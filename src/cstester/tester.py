import curses, os, re, shlex, shutil, subprocess, sys, yaml
from difflib import unified_diff
from inspect import getdoc
from types import TracebackType
from typing import List, Optional, Type, Tuple
from zipfile import ZipFile
from .win import CursesScreen, WinOpt
from .configmgr import ConfigManager
from .extractor import Extractor
from .utils import getfilehash, getgroups, expandnumrange, runprocess

'''
    Copyright (C) 2026  Chase Phelps

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

class CSTester:
  '''
  Main class to drive testing Computer Science submissions
  '''
  def __init__(self, argv: Optional[List[str]]=None) -> None:
    '''
    Initialize the CSTester instance

    Args:
      argv (Optional[List[str]]): Optional command-line arguments

    If arguments are given, we expect **argv[1]** to be a configuration file
    '''
    #: The active :py:class:`.CursesScreen` object
    self.scr = CursesScreen()
    #: The actual name of this class
    self.name = type(self).__name__
    #: An instance of :py:class:`.ConfigManager`,
    #: this class provides an abstraction of :py:class:`.CSTesterConfig`
    self.cfg = ConfigManager(self.scr) if argv is None or len(argv) != 2 \
          else ConfigManager(self.scr, argv[1])

  def __enter__(self) -> 'CSTester':
    self.scr.initscr()
    return self

  def __exit__(self,
              type: Optional[Type[BaseException]],
              value: Optional[BaseException],
              traceback: Optional[TracebackType]) -> Optional[bool]:
    if self.scr is not None:
      self.scr.cleanup()
    self.scr = None

  def __del__(self) -> None:
    if self.scr is not None:
      self.scr.cleanup()
    self.scr = None

  def getgrouplists(self) -> Tuple[List[str], List[str], List[str]]:
    '''
    Return included, excluded, and all group lists (expanded)

    Returns:
      Tuple[List[str], List[str], List[str]]: (included, excluded, allgroups)
    '''
    return (expandnumrange(self.cfg.include),
            expandnumrange(self.cfg.exclude),
            expandnumrange(','.join(getgroups(self.cfg.phasedir))))

  def getfilteredgroups(self) -> List[str]:
    '''
    Return the filtered list of groups after applying include/exclude rules

    Returns:
      List[str]: Filtered group identifiers as strings
    '''
    included, excluded, groups = self.getgrouplists()
    if included:
      groups = [group for group in groups if group in included]
    if excluded:
      groups = [group for group in groups if not group in excluded]
    return groups

  def makeclean(self) -> None:
    '''
    Remove files matching the configured clean patterns within group directories
    '''
    groups = self.getfilteredgroups()
    patterns = [re.compile(p) for p in self.cfg.cleanfiles]
    count = 0
    for group in groups:
      groupdir = os.path.join(self.cfg.phasedir, f'group_{group}')
      if not os.path.isdir(groupdir):
        continue
      for root, dirs, files in os.walk(groupdir, topdown=True):
        for file in files:
          if any(p.match(file) for p in patterns):
            os.unlink(os.path.join(root, file))
            count += 1
    self.scr.window(
      WinOpt.SHOWCURS|WinOpt.RETURNANY,
      title='Make clean', body=[f'Deleted {count} files'],
    )

  def help_runtests(self, title: str) -> None:
    '''
    Display an informational window describing the runtests view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.runtests).strip('\n').split('\n'),
    )

  def runtests(self) -> None:
    '''
    Run tests for each group using the configured test command

    Failures are collected and reported

    Navigation and control commands available:
      - Previous group: a A b B
      - Next group: d D n N
      - Continue in direction: <SPACE>
      - Quit: <ESC>
    '''
    title = f'{self.name} - Run Tests'
    opts = {
            'runall': 'Run all tests',
            'runsub': 'Run test subset',
            'modsub': 'Modify test subset',
            'return': 'Return to evaluation menu',
            }
    keys = list(opts.keys())
    values = list(opts.values())
    choices = list(opts.values())
    exitkeys = ('a', 'A', 'b', 'B',
                'd', 'D', 'n', 'N', ' ') + CursesScreen.returnkeys
    helpstr = 'Previous: [aAbB], Next: [dDnN] Continue: [ ], Help: [?hH]'
    cases = [os.path.splitext(case)[0] for case in self.cfg.cases]
    cases = {case :
              (os.path.join(self.cfg.casedir, case+self.cfg.caseext),
                ( os.path.join(self.cfg.expdir, case+self.cfg.expext) \
                if case+self.cfg.expext in self.cfg.exps \
                else None )
              )
              for case in cases
            }
    runcases = cases
    def getdisabled() -> List:
      disabled = []
      if not runcases:
        disabled.append(keys.index('runsub'))
      return disabled
    groups = self.getfilteredgroups()
    group = 0
    # we only go left or right, start going right from group index 0
    right = True
    readme = ''
    basecmd = self.cfg.testcmd
    cmd = basecmd
    filename = ''
    hpos = 0
    while True:
      if group < 0:
        group = len(groups)-1
      elif group >= len(groups):
        group = 0
      groupdir = os.path.join(self.cfg.phasedir, f'group_{groups[group]}')
      if not os.path.isdir(groupdir):
        if right:
          group += 1
        else:
          group -= 1
        continue
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.RETURNDEL|WinOpt.USEHELP,
        title=title,
        disabled=getdisabled(),
        returnkeys=exitkeys,
        helpstr=helpstr,
        body=[f'Group {groups[group]}', ''],
        choices=choices,
        hpos=hpos,
      )
      if c == 'KEY_DC':
        if hpos == keys.index('modsub'):
          choices[hpos] = f'{values[hpos]}: (unset)'
        continue
      if c in CursesScreen.cancelkeys or keys[hpos] == 'return':
        break
      if c in ('a','A','b','B'):
        right = False
        group -= 1
        continue
      if c in ('d','D','n','N'):
        right = True
        group += 1
        continue
      if c == ' ':
        if right:
          group += 1
        else:
          group -= 1
        continue
      if keys[hpos] == 'modsub':
        _, _, c = self.scr.window(
          WinOpt.RETURNMUL,
          title=title,
          body=['Select subset of cases to use:'],
          choices=['Confirm selection',''] + list(cases.keys()),
        )
        if c in CursesScreen.cancelkeys:
          pass
        else:
          runcases = {case:cases[case] for case in c}
          choices[hpos] = values[hpos]
          if not runcases:
            choices[hpos] += ': (unset)'
          else:
            choices[hpos] += f': {', '.join([k for k in runcases.keys()])}'
        continue
      if keys[hpos] == 'runall':
        usecases = cases
      elif keys[hpos] == 'runsub':
        usecases = runcases
      pwd = os.getcwd()
      os.chdir(groupdir)
      errors = []
      for case in usecases:
        if '@case@' in basecmd:
          cmd = basecmd.replace('@case@', cases[case][0])
        else:
          filename = cases[case][0]
        out, err, ret = runprocess(cmd=shlex.split(cmd), filename=filename)
        # bad exit, accumulate errors
        if ret != 0:
          if errors:
            errors.append('')
          errors.append(f'Test {case}')
          if out.strip():
            errors.append('stdout:')
            errors.extend(out.strip().split('\n'))
            errors.append('stderr:')
          errors.extend(err.strip().split('\n'))
        # normal exit but no expected output
        else:
          if cases[case][1] is None:
            # lhs will be test input
            with open(cases[case][0], 'r') as infile:
              lhs = [line.rstrip() for line in infile.readlines()]
            ltitle = f'{case} input'
          else:
            # lhs will be expected output
            with open(cases[case][1], 'r') as infile:
              lhs = [line.rstrip() for line in infile.readlines()]
            ltitle = f'{case} expected output'
          # rhs is actual output
          rtitle = 'actual output'
          rhs = [line.rstrip() for line in err.split('\n')] + \
                [line.rstrip() for line in out.split('\n')]
          self.scr.diffwindow((title, ltitle, lhs, rtitle, rhs))
      os.chdir(pwd)
      if errors:
        self.scr.window(
          WinOpt.RETURNKEY|WinOpt.TEXTBOX,
          title=f'{title}: Group {groups[group]}',
          choices=errors,
        )

  def runsearch(self) -> None:
    '''
    Search for configured string patterns within files (visual grep)

    Uses ``searchstrs`` and ``searchfiles`` from :py:attr:`.cfg`
    to select files and patterns;
    files are scanned line-by-line as text for search patterns
    '''
    title = f'{self.name} - Run Search Strings'
    pwd = os.getcwd()
    groups = self.getfilteredgroups()
    ngroups = len(groups)
    nmatches = 0
    body = []
    strpatterns = [re.compile(p) for p in self.cfg.searchstrs]
    filepatterns = [re.compile(p) for p in self.cfg.searchfiles]
    for i, group in enumerate(groups):
      groupdir = os.path.join(self.cfg.phasedir, f'group_{group}')
      if not os.path.isdir(groupdir):
        continue
      self.scr.statuswindow(title, f'{i} of {ngroups} complete', body)
      groupmatches = False
      for root, dirs, files in os.walk(groupdir, topdown=True):
        for file in files:
          if not any(p.match(file) for p in filepatterns):
            continue
          file = os.path.join(root, file)
          matches = {}
          with open(file, 'r') as infile:
            for linenum, line in enumerate(infile.readlines()):
              line = line.rstrip()
              if any(p.search(line) for p in strpatterns):
                matches[linenum] = line
                nmatches += 1
          if matches:
            if body:
              body.append('')
            if not groupmatches:
              body.append(f'Group {group}:')
              groupmatches = True
            body.append(file.removeprefix(groupdir).lstrip(os.path.sep))
            for match in matches:
              body.append(f'{match+1:3d}: {matches[match]}')
          self.scr.statuswindow(title, f'Group {i+1} of {ngroups}', body)
    self.scr.clearkeys()
    if body:
      body = ['Matches found:',''] + body
      self.scr.window(
        WinOpt.RETURNKEY|WinOpt.TEXTBOX,
        title=title,
        choices=body,
        footer=f'{nmatches} matches',
      )

  def runpreparation(self) -> None:
    '''
    Run a sequence of preparation commands in each group directory

    Commands run in order, on failure subsequent commands are skipped

    Failures are collected and reported
    '''
    title = f'{self.name} - Run Preparation'
    pwd = os.getcwd()
    groups = self.getfilteredgroups()
    ngroups = len(groups)
    body = []
    for i, group in enumerate(groups):
      groupdir = os.path.join(self.cfg.phasedir, f'group_{group}')
      if not os.path.isdir(groupdir):
        continue
      self.scr.statuswindow(title, f'{i} of {ngroups} complete', body)
      os.chdir(groupdir)
      for i, cmd in enumerate(self.cfg.prepcmds):
        cmd = shlex.split(cmd)
        _, err, ret = runprocess(cmd, getout=False)
        if ret == 0:
          continue
        if body:
          body.append('')
        body.extend([f'Group {group}:',
                    f'{i}: {shlex.join(cmd)}'])
        body.extend([e.strip() for e in err.split('\n') if e.strip() != ''])
        break
    os.chdir(pwd)
    self.scr.clearkeys()
    if body:
      body = ['Commands:'] + \
            [f'{i}: {cmd}' for i,cmd in enumerate(self.cfg.prepcmds)] + \
            [''] + \
            body
      self.scr.window(
        WinOpt.RETURNKEY|WinOpt.TEXTBOX,
        title=title,
        choices=body,
        footer='Preparation failures',
      )

  def help_lessreadmes(self, title: str) -> None:
    '''
    Display an informational window describing the lessreadmes view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.lessreadmes).strip('\n').split('\n'),
    )

  def lessreadmes(self) -> None:
    '''
    Display README files from each group directory

    Navigation and control Commands available:
      - Previous group: a A b B
      - Next group: d D n N
      - Continue in direction: <SPACE>
      - Quit: <ESC>
    '''
    title = f'{self.name} - Read READMEs'
    exitkeys = ('a', 'A', 'b', 'B',
                'd', 'D', 'n', 'N', ' ') + CursesScreen.returnkeys
    helpstr = 'Previous: [aAbB], Next: [dDnN] Continue: [ ], Help: [?hH]'
    groups = self.getfilteredgroups()
    group = 0
    # we only go left or right, start going right from group index 0
    right = True
    readmename = self.cfg.readmename
    while True:
      if group < 0:
        group = len(groups)-1
      elif group == len(groups):
        group = 0
      groupdir = os.path.join(self.cfg.phasedir, f'group_{groups[group]}')
      readme = os.path.join(groupdir, readmename)
      if not os.path.isfile(readme):
        _, _, c = self.scr.window(
          WinOpt.RETURNKEY|WinOpt.USEHELP,
          title=f'{title}: Group {groups[group]}',
          err=[f'Group {groups[group]}: missing {readmename}'],
          helpstr=helpstr,
          returnkeys=exitkeys,
        )
      else:
        with open(readme, 'r') as infile:
          body = [line.rstrip() for line in infile.readlines()]
        _, _, c = self.scr.window(
          WinOpt.RETURNKEY|WinOpt.TEXTBOX|WinOpt.USEHELP,
          title=f'{title}: Group {groups[group]}',
          choices=body,
          helpstr=helpstr,
          returnkeys=exitkeys,
        )
      if c in CursesScreen.cancelkeys:
        break
      elif c in ('a', 'A', 'b', 'B'):
        group -= 1
        right = False
      elif c in ('d', 'D', 'n', 'N'):
        group += 1
        right = True
      elif c == ' ':
        if right:
          group += 1
        else:
          group -= 1

  def freezefiles(self) -> None:
    '''
    Create a frozen snapshot of matching files

    Matching files are archived (zip) and their hashes stored,
    performed before modifications can allow patch generation
    '''
    hashfile = os.path.join(self.cfg.phasedir,'frozen.hash')
    zipfile = os.path.join(self.cfg.phasedir,'frozen.zip')
    hashes = {}
    patterns = [re.compile(p) for p in self.cfg.freezefiles]
    for root, dirs, files in os.walk(self.cfg.phasedir, topdown=True):
      for file in files:
        if any(p.match(file) for p in patterns):
          src = os.path.join(root, file)
          hashes[src] = getfilehash(src)
    if hashes:
      with open(hashfile,'w') as hashfile:
        for k,v in hashes.items():
          hashfile.write(f'{k}\n{v}\n')
      with ZipFile(zipfile,'w') as zipfile:
        for src in hashes:
          zipfile.write(src)
    elif os.path.isfile(hashfile):
      os.unlink(hashfile)
    self.scr.window(
      WinOpt.SHOWCURS|WinOpt.RETURNANY,
      title='Freeze Files',
      body=[f'Created hashes for {len(hashes)} files'],
    )
    return len(hashes) > 0

  def mkpatches(self) -> None:
    '''
    Detect modification of frozen files and generate diff patches

    Patches can be applied with the ``patch`` command
    or distributed to show changes, e.g., fixes required for compilation
    '''
    hashfile = os.path.join(self.cfg.phasedir,'frozen.hash')
    zipfile = os.path.join(self.cfg.phasedir,'frozen.zip')
    # the hashfile contents
    # we will leave the original file as-is in the frozen.zip
    # if we have modified files we will update the frozen hash though
    frozenhash = ''
    # patch file list
    patches = []
    with open(hashfile, 'r') as infile:
      while True:
        src = infile.readline()
        if not src:
          break
        src = src.rstrip()
        old = infile.readline().rstrip()
        if not os.path.isfile(src) or old == getfilehash(src):
          continue
        # get the original contents
        with ZipFile(zipfile,'r') as zfile:
          zname = [z.filename for z in zfile.infolist() \
                              if src.endswith(z.filename)]
          if not zname:
            continue
          old = zfile.read(name=zname[0])
        old = old.decode().rstrip().split('\n')
        # the new contents
        with open(src, 'r') as new:
          new = [line.rstrip() for line in new.readlines()]
        # generate the patch
        patch = unified_diff(old, new,
                            fromfile=f'a/{os.path.basename(src)}',
                            tofile=f'b/{os.path.basename(src)}', lineterm='')
        src = f'{src}.patch'
        with open(src, 'w') as outfile:
          outfile.write('\n'.join(patch)+'\n')
        patches.append(src.removeprefix(self.cfg.phasedir).lstrip(os.path.sep))
    if patches:
      footer = 'Press enter to continue . . . '
      self.scr.window(
        WinOpt.RETURNKEY|WinOpt.TEXTBOX|WinOpt.SHOWCURS,
        title='Make patches',
        body=[f'Made {len(patches)} patches:'],
        choices=patches,
        footer=footer,
      )
    else:
      self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNANY,
        title='Make patches',
        body=['No modified files found'],
      )

  def help_phasemenu(self, title: str) -> None:
    '''
    Display an informational window describing the phasemenu view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.phasemenu).strip('\n').split('\n'),
    )

  def phasemenu(self) -> None:
    '''
    Menu to configure and setup the phase directory from a phase zip

    The phase zip contains group submission zips

    Options:
      keyfile: optional mapping to associate zip-filename parts with groups
      group regex: required pattern to extract group number
      zip include/exclude patterns with target locations
    '''
    # the title for each window
    title = f'{self.name} - Phase Directory Menu'
    # the choices
    opts = {
            'extract':'Extract phasezip to Phase dir',
            'phasedir':'Phase directory',
            'phasezip':'Phase zip',
            'keyfile':'Extraction Keyfile',
            'groupre_str':'Group regex',
            'zipinclude_strs':'Zip include',
            'zipexclude_strs':'Zip exclude',
            'return':'Return to main menu',
            }
    keys = list(opts.keys())
    values = list(opts.values())
    def getdisabled() -> List:
      disabled = []
      if any([not self.cfg.isset(attr) for attr \
                            in ('phasedir','phasezip','groupre_str')]):
        disabled.append(keys.index('extract'))
      return disabled
    choices = [opts[o] if not self.cfg.has(o) \
                else opts[o]+': (unset)' if not self.cfg.isset(o) \
                else opts[o]+f': {self.cfg.get(o)}' for o in opts]
    hpos = 0
    while True:
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.RETURNDEL|WinOpt.USEHELP,
        title=title,
        disabled=getdisabled(),
        choices=choices,
        hpos=hpos,
      )
      if c == 'KEY_DC':
        if self.cfg.has(keys[hpos]) and self.cfg.isset(keys[hpos]):
          self.cfg.resetattr(keys[hpos])
      # allow to quit on escape, q, or Q:
      elif c in CursesScreen.cancelkeys or keys[hpos] == 'return':
        break
      elif self.cfg.has(keys[hpos]):
        self.cfg.modifyconf(keys[hpos], title)
      elif keys[hpos] == 'extract':
        conf = self.cfg.conf
        with Extractor(self.scr) as extractor:
          extractor.extractphasezip(conf.phasedir,
                                    conf.phasezip,
                                    conf.keyfile,
                                    conf.groupre_str,
                                    conf.zipinclude_strs,
                                    conf.zipexclude_strs)
      if self.cfg.has(keys[hpos]):
        v = self.cfg.get(keys[hpos])
        choices[hpos] = values[hpos] + (': (unset)' if not v else f': {v}')

  def help_groupmenu(self, title: str) -> None:
    '''
    Display an informational window describing groupmenu's view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.groupmenu).strip('\n').split('\n'),
    )

  def groupmenu(self) -> None:
    '''
    Menu for managing group directories:
    include/exclude groups, freeze files, create patches, and clean files.

    Include/exclude lists use comma-separated numbers/ranges, e.g., 1,4-9
    '''
    # the title for each window
    title = f'{self.name} - Group Directories Menu'
    # the choices
    opts = {
            'chooseinc':'Select groups to only include',
            'include':'Enter groups to only include',
            'chooseexc':'Select groups to exclude',
            'exclude':'Enter groups to exclude',
            'freeze':'Freeze files',
            'freezefiles':'Freeze file regexes',
            'mkpatch':'Make patches for modifications since freeze',
            'clean':'Clean files',
            'cleanfiles':'Clean files regexes',
            'return':'Return to main menu',
            }
    keys = list(opts.keys())
    values = list(opts.values())
    def getdisabled() -> List:
      disabled = []
      if not self.cfg.isset('freezefiles'):
        disabled.append(keys.index('freeze'))
      if not os.path.isfile(os.path.join(self.cfg.phasedir,'frozen.hash')):
        disabled.append(keys.index('mkpatch'))
      if not self.cfg.isset('cleanfiles'):
        disabled.append(keys.index('clean'))
      return disabled
    choices = [opts[o] if not self.cfg.has(o) \
                else opts[o]+': (unset)' if not self.cfg.isset(o) \
                else opts[o]+f': {self.cfg.get(o)}' for o in opts]
    allgroups = getgroups(self.cfg.phasedir)
    hpos = 0
    while True:
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.RETURNDEL|WinOpt.USEHELP,
        title=title,
        disabled=getdisabled(),
        choices=choices,
        hpos=hpos,
      )
      if c == 'KEY_DC':
        if self.cfg.has(keys[hpos]) and self.cfg.isset(keys[hpos]):
          self.cfg.resetattr(keys[hpos])
      # allow to quit on escape, q, or Q:
      elif c in CursesScreen.cancelkeys or keys[hpos] == 'return':
        break
      elif self.cfg.has(keys[hpos]):
        self.cfg.modifyconf(keys[hpos], title)
      elif keys[hpos] in ['chooseinc','chooseexc']:
        chosen = []
        attr = 'include' if keys[hpos] == 'chooseinc' else 'exclude'
        if self.cfg.isset(attr):
          chosen = expandnumrange(self.cfg.get(attr))
          chosen = [f'Group {group}' for group in chosen if group in allgroups]
        _, _, groups = self.scr.window(
          WinOpt.RETURNMUL,
          title=title,
          chosen=chosen,
          body=[f'Select groups to {attr}:',''],
          choices=['Confirm selection',''] + \
          [f'Group {group}' for group in allgroups],
        )
        if isinstance(groups, list):
          groups = ','.join([group.split(' ')[-1] for group in groups])
          groups = self.cfg.verifiednumrange(groups)
          setattr(self.cfg.conf, attr, groups)
          c = keys.index(attr)
          choices[hpos+1] = values[hpos+1] + (': (unset)' if not groups \
                                                          else f': {groups}')
      elif keys[hpos] == 'freeze':
        self.freezefiles()
      elif keys[hpos] == 'mkpatch':
        self.mkpatches()
      elif keys[hpos] == 'clean':
        self.makeclean()
      if self.cfg.has(keys[hpos]):
        v = self.cfg.get(keys[hpos])
        choices[hpos] = values[hpos] + (': (unset)' if not v else f': {v}')

  def help_evalmenu(self, title: str) -> None:
    '''
    Display an informational window describing the evalmenu view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.evalmenu).strip('\n').split('\n'),
    )

  def evalmenu(self) -> None:
    '''
    Menu for running evaluation tasks:
    run tests, prepare, clean, search, and view READMEs
    '''
    title = f'{self.name} - Evaluation Menu'
    opts = {
            'runtest':'Run tests',
            'testcmd':'Test command',
            'runprep':'Run prepare commands',
            'prepcmds':'Preparation commands',
            'makeclean':'Clean files',
            'runsearch':'Run search strings in files',
            'searchstrs':'Search string patterns',
            'searchfiles':'Search files for strings',
            'rdreadme':'Read readme files',
            'readmename':'Set readme name',
            'return':'Return to main menu',
            }
    keys = list(opts.keys())
    values = list(opts.values())
    choices = [opts[o] if not self.cfg.has(o) \
                else opts[o]+': (unset)' if not self.cfg.isset(o) \
                else opts[o]+f': {self.cfg.get(o)}' for o in opts]
    def getdisabled() -> List:
      disabled = []
      if not self.cfg.testcmd:
        disabled.append(keys.index('runtest'))
      if not self.cfg.prepcmds:
        disabled.append(keys.index('runprep'))
      if not self.cfg.cleanfiles:
        disabled.append(keys.index('makeclean'))
      if not self.cfg.searchstrs or not self.cfg.searchfiles:
        disabled.append(keys.index('runsearch'))
      if not self.cfg.readmename:
        disabled.append(keys.index('rdreadme'))
      return disabled
    hpos = 0
    while True:
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.USEHELP,
        title=title,
        disabled=getdisabled(),
        choices=choices,
        hpos=hpos,
      )
      if c in CursesScreen.cancelkeys or keys[hpos] == 'return':
        return
      elif keys[hpos] == 'runtest':
        self.runtests()
      elif keys[hpos] == 'runprep':
        self.runpreparation()
      elif keys[hpos] == 'makeclean':
        self.makeclean()
      elif keys[hpos] == 'runsearch':
        self.runsearch()
      elif keys[hpos] == 'rdreadme':
        self.lessreadmes()
      elif self.cfg.has(keys[hpos]):
        self.cfg.modifyconf(keys[hpos], title=title)
      if self.cfg.has(keys[hpos]):
        v = self.cfg.get(keys[hpos])
        choices[hpos] = values[hpos] + (': (unset)' if not v else f': {v}')

  def help_configure(self, title: str) -> None:
    '''
    Display an informational window describing the configure view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.configure).strip('\n').split('\n'),
    )

  def configure(self) -> None:
    '''
    Configuration menu to display and modify configuration values

    Accepted value types include
    strings,
    directory or file paths,
    lists,
    and dicts.

    Validation may include
    regex compilation,
    number/range parsing,
    and command verification.
    '''
    title = f'{self.name} - Configuration'
    opts = {
            'phasedir':'Phase dir',
            'casedir':'Cases dir',
            'caseext':'Cases ext',
            'expdir':'Exp dir',
            'expext':'Exp ext',
            'include':'Include only',
            'exclude':'Exclude only',
            'testcmd':'Testing command',
            'phasezip':'Phase zip',
            'keyfile':'Keyfile',
            'groupre_str':'Regex to get group from group.zip',
            'zipinclude_strs':'Regex dict of patterns to move',
            'zipexclude_strs':'Regex list of patterns to exclude',
            'return':'Return to main menu',
            }
    keys = list(opts.keys())
    values = list(opts.values())
    choices = [opts[o] if not self.cfg.has(o) \
                else opts[o]+': (unset)' if not self.cfg.isset(o) \
                else opts[o]+f': {self.cfg.get(o)}' for o in opts]
    hpos = 0
    while True:
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.RETURNDEL|WinOpt.USEHELP,
        title=title,
        choices=choices,
        hpos=hpos,
      )
      if c in CursesScreen.cancelkeys or keys[hpos] == 'return':
        break
      elif c == 'KEY_DC':
        if self.cfg.has(keys[hpos]) and self.cfg.isset(keys[hpos]):
          self.cfg.resetattr(keys[hpos])
      elif self.cfg.has(keys[hpos]):
        self.cfg.modifyconf(keys[hpos], title=title)
      if self.cfg.has(keys[hpos]):
        v = self.cfg.get(keys[hpos])
        choices[hpos] = values[hpos] + (': (unset)' if not v else f': {v}')

  def help_mainmenu(self, title: str) -> None:
    '''
    Display an informational window describing the mainmenu view
    '''
    self.scr.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.mainmenu).strip('\n').split('\n'),
    )

  def mainmenu(self) -> None:
    '''
    Main menu entry point that links to phase, groups, evaluation,
    and configuration submenues. Saving and Loading from YAML is supported
    '''
    # the title for each window
    title = f'{self.name} - Main Menu'
    # the choices
    opts = {
            'phase':'Phase directory setup',
            'group':'Groups',
            'eval':'Evaluation menu',
            'config':'Edit/view Configuration',
            'save':'Save current configuration',
            'load':'Load a configuration',
            'quit':'Quit',
            }
    keys = list(opts.keys())
    def getdisabled() -> List:
      disabled = []
      if not os.path.isfile(f'{self.cfg.phasedir}/x.log'):
        disabled.append(keys.index('group'))
        disabled.append(keys.index('eval'))
      return disabled
    choices = [opts[o] for o in opts]
    hpos = 0
    while True:
      _, hpos, c = self.scr.window(
        WinOpt.RETURNKEY|WinOpt.USEHELP,
        title=title,
        disabled=getdisabled(),
        choices=choices,
        hpos=hpos,
      )
      # allow to quit on escape, q, or Q:
      if c in CursesScreen.cancelkeys or keys[hpos] == 'quit':
        break
      elif keys[hpos] == 'phase':
        self.phasemenu()
      elif keys[hpos] == 'group':
        self.groupmenu()
      elif keys[hpos] == 'eval':
        self.evalmenu()
      elif keys[hpos] == 'config':
        self.configure()
      elif keys[hpos] == 'save':
        self.cfg.save()
      elif keys[hpos] == 'load':
        self.cfg.load()
