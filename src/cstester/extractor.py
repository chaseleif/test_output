import filecmp, os, re, shutil, stat, sys
from argparse import ArgumentParser
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Dict, List, Literal, Optional, Type, Tuple
from zipfile import BadZipFile, ZipFile
from .win import CursesScreen, WinOpt

class Extractor:
  '''
  Class to extract submissions
  '''
  def __init__(self, scr: Optional['CursesScreen']=None) -> None:
    '''
    This class may either be given a screen or will make its own
    '''
    self.scr = CursesScreen() if scr is None else scr

  def __enter__(self) -> 'Extractor':
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

  def getgroupfiles(self,
                    tempdir: str,
                    keyfile: str,
                    groupre: str,
                    steps: List[str]) -> Tuple[List[str], Dict[str,str]]:
    '''
    This method will return a tuple which maps groups to zip files

    The best way to get a group number from a zip filename is with a regex

    In case the filename isn't correct, we accept an optional keyfile

    Keys are extracted from the keyfile with the regex:
      | ``^([0-9]+),.*:([^:]+)$``

    When a group number can't be inferred, the user is prompted for input

    Decisions are recorded in the extraction log

    Steps performed in this method:

    1) Obtain any keys from the optional keyfile
    2) Iterate through files in tempdir

      skip (but log) non-zip files

    3) Attempt a group regex match
    4) If regex match fails, attempt to use the keyfile
    5) If unable to automatically determine group, prompt for input

      Use of keyfile/prompts recorded in logs

    6) Verify a single submission for each group

      Groups with multiple submissions prompt for which to keep

    7) Return the logs and group->file mapping
    '''
    title = 'Extraction: getgroupfiles'
    logs = []
    keys = {}
    if keyfile is not None and os.path.isfile(keyfile):
      keyregex = re.compile(r'^(0|[1-9][0-9]*)(?:,.*)?:([^:]+)$')
      # the key is what we search for (all after final colon, group 1)
      # keys[key] is the group number (all before first comma, group 0)
      try:
        with open(keyfile, 'r') as infile:
          for line in infile.readlines():
            line = line.rstrip().lower()
            match = keyregex.match(line.rstrip().lower())
            if match:
              keys[match.groups()[1]] = int(match.groups()[0])
      except Exception as e:
        pass
      logs.append(f'{len(keys)} keys obtained from the keyfile')
    else:
      logs.append(f'No keyfile used')
    status = 'Collecting group numbers and zips'
    self.scr.statuswindow(title, status, logs)
    groups = {}
    # allow to not have a group regex
    if not groupre:
      # this will match any file not ending with p, so will not match
      groupre = re.compile('.*[^p]$', re.IGNORECASE)
    else:
      # compile the provided group regex
      groupre = re.compile(groupre, re.IGNORECASE)
    # if we don't match with regex we'll try keys from keyfile
    for filename in os.listdir(tempdir):
      # a submission could include non-zip files, e.g., a txt or pdf
      if not filename.lower().endswith('.zip'):
        logs.append(f'skipping non-zip file {filename}')
        continue
      # try regex
      match = groupre.match(filename)
      if match:
        group = int(match.groups()[0])
      else:
        # search through keys
        groupchoices = {}
        for key in keys:
          if key in filename.lower():
            # keys[key] is group number, key is something in the filename
            if keys[key] not in groupchoices:
              groupchoices[keys[key]] = key
            else:
              groupchoices[keys[key]] += ', ' + key
        # no matches found
        if len(groupchoices) == 0:
          if steps:
            group = steps.pop(0)
            group = int(group) if group.isnumeric() else None
          else:
            while True:
              group = self.scr.getinput(title,
                                        f'Enter group for file: {filename}')
              if group is None or not group.isnumeric():
                group = None
                break
              group = int(group)
              _, _, c = self.scr.window(
                WinOpt.SHOWCURS|WinOpt.RETURNANY,
                title = title,
                err = [filename],
                body = [f'You entered group \"{group}\"'],
                footer = 'Accept? [Y/n] ',
              )
              if c in self.scr.cancelkeys or c not in ('N', 'n'):
                break
            self.scr.statuswindow(title, status, logs)
          logs.append(f'*{group} entered for group when none found: {filename}')
        # 1 match found
        elif len(groupchoices) == 1:
          group = list(groupchoices.keys())[0]
          logs.append(f'Group {group} inferred with 1 choice for {filename}')
        else:
          # > 1 match found
          choices = [f'{number}) {members}' \
                      for number,members in groupchoices.items()]
          if steps:
            group = steps.pop(0)
            group = int(group) if group.isnumeric() else None
          else:
            _, g, c = self.scr.window(
              WinOpt.RETURNKEY,
              title=title,
              choices=choices,
              body=[f'Select group for {filename}'],
            )
            if c not in CursesScreen.cancelkeys:
              group = int(choices[g].split(')')[0])
            else:
              group = None
            self.scr.statuswindow(title, status, logs)
          logs.append(f'*{group} chosen for group for {filename} from:')
          logs.extend(choices)
        if group is None:
          continue
      # add singles to groups dict or append to lists within
      if group in groups:
        if not isinstance(groups[group], list):
          groups[group] = [groups[group]]
        groups[group].append(filename)
      else:
        groups[group] = filename
    # sort ascending by group number
    groups = dict(sorted(groups.items()))
    status = 'Checking groups for multiple submissions'
    self.scr.statuswindow(title, status, logs)
    for group in groups:
      # if it isn't a list there is only 1 filename
      if not isinstance(groups[group], list):
        continue
      # check whether the submissions are identical
      different = False
      for i in range(1, len(groups[group])):
        if not filecmp.cmp(os.path.join(tempdir, groups[group][0]),
                          os.path.join(tempdir, groups[group][i]),
                          shallow=False):
          different = True
          break
      # the group had multiple identical submissions, just take the first
      if not different:
        groups[group] = groups[group][0]
        continue
      groups[group].sort()
      logs.append(f'Group {group}:')
      logs.extend(groups[group])
      if steps:
        i = steps.pop(0)
        i = int(i) if i.isnumeric() else None
      else:
        _, i, c = self.scr.window(
          WinOpt.RETURNKEY,
          title=title,
          choices=[str(g) for g in groups[group]],
          body=[f'Select group for {filename}'],
        )
      if c in CursesScreen.cancelkeys:
        logs.append('*None chosen (group removed)')
        groups.remove(group)
      else:
        groups[group] = groups[group][i]
        logs.append(f'*{i} chosen')
      self.scr.statuswindow(title, status, logs)
    logs.append(f'Using {len(groups)} group/file pairs')
    return logs, groups

  def extract(self,
              tempdir: str,
              phasedir: str,
              keyfile: str,
              groupre: str,
              include: Dict[str, str],
              _exclude: List[str],
              steps: List[str]) -> List[str]:
    '''
    This method extracts individual zip files to respective group directories

    We get a group->file mapping from ``getgroupfiles``, then, for each group,

    1) The extraction path is ``phasedir/group_n``

      where n is a non-negative integer, i.e., ``[0-9]+``

    2) Iterate through the zipfile's member list
    3) Exclude symlinks and files matching an exclude pattern
    4) Refuse to extract zips with an unrealistic compression ratio
    5) Extract selected members to a temporary directory
    6) Set owner-only permissions RWX for directories and RW for files
    7) Ensure directories exist rather than filenames with directory parts
    8) Ensure no single top-level directory (move files up)
    9) Track paths for any file wanted in a specific location
    10) Don't save duplicate files
    11) Move files into destination group directory
    12) Save extraction log and original zip in group directory
    '''
    title = 'Extraction: extract'
    logs, groups = self.getgroupfiles(tempdir, keyfile, groupre, steps)
    # groups should have a length
    if len(groups) == 0:
      self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNANY,
        title=title,
        body=['Can\'t complete extraction'],
        err=[f'No group zip files found'],
      )
      return []
    # permissions for extracted output
    dirchmod = stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR
    filechmod = stat.S_IRUSR|stat.S_IWUSR
    _exclude = [re.compile(pattern, re.IGNORECASE) for pattern in _exclude]
    exclude = lambda name: name == '..' or \
                          any(pattern.match(name) for pattern in _exclude)
    include = {re.compile(k):v for k,v in include.items()}
    # dst names are stripped of bad chars and lowercased
    dstname = lambda name: re.sub(r'[^_0-9a-z\.]', '', name.lower())
    err = []
    # get group numbers and each group's zip file
    for i, group in enumerate(groups):
      self.scr.statuswindow(title, 'Remaining: ' + '.' * (len(groups)-i),
                            logs, err)
      # group zip file
      zipname = os.path.join(tempdir, groups[group])
      # extract to xpath
      xpath = os.path.join(phasedir, f'group_{group}')
      os.makedirs(xpath, exist_ok=True)
      # start in a temp path
      with TemporaryDirectory() as grouptemp:
        try:
          os.chmod(zipname, filechmod)
          # extract their zip (excluding symlinks)
          with ZipFile(zipname, 'r') as archive:
            members = []
            excludelist = []
            symlist = []
            compress_size = 0
            file_size = 0
            for member in archive.infolist():
              if member.is_dir():
                continue
              if stat.S_ISLNK(member.external_attr>>16):
                symlist.append(member.filename)
                logs.append(f'IGNORING Group {group} link: {member.filename}')
                continue
              # zips created in Windows will have \\ separators
              # PureWindowsPath can split both proper and Windows paths
              if any(exclude(part) \
                      for part in PureWindowsPath(member.filename).parts):
                excludelist.append(member.filename)
              else:
                compress_size += member.compress_size
                file_size += member.file_size
                members.append(member.filename)
            if compress_size > 0:
              ratio = file_size / compress_size
            else:
              ratio = -1
            # record the zip info
            with open(f'{xpath}/sub.nfo','w') as outfile:
              outfile.write(os.path.basename(zipname)+'\n')
              outfile.write(f'{file_size}B / {compress_size}B = {ratio:.2f}x\n')
              if symlist:
                outfile.write('Excluded sym links:\n')
                outfile.write('\n'.join(sorted(symlist))+'\n')
              if members:
                outfile.write('Extracting:\n')
                outfile.write('\n'.join(sorted(members))+'\n')
              if excludelist:
                outfile.write('Excluded:\n')
                outfile.write('\n'.join(sorted(excludelist))+'\n')
            if ratio < 0:
              msg = f'SKIPPING Group {group} zip file: ' + \
                    f'{zipname} had no compressed size'
              raise BadZipFile(msg)
            if ratio > 6:
              msg = f'SKIPPING Group {group} zip file: ' + \
                    f'{zipname} bad compression ratio {ratio:.2f}x'
              raise BadZipFile(msg)
            archive.extractall(path=grouptemp, members=members)
        except Exception as e:
          shutil.move(zipname, f'{xpath}/group{group}.zip')
          logs.append('EXCEPTION opening/extracting archive')
          logs.append(f'Group {group}: {os.path.basename(zipname)}')
          e = str(e).strip()
          logs.append(e)
          err += [m.strip() for m in re.split(r'[:\n]+', e)]
          continue
        # fix chmod
        for dirpath, dirnames, filenames in os.walk(grouptemp):
          for name in dirnames:
            os.chmod(os.path.join(dirpath, name), dirchmod)
          for name in filenames:
            os.chmod(os.path.join(dirpath, name), filechmod)
        # files with windows pathnames won't be in directories
        for name in list(os.listdir(grouptemp)):
          if PureWindowsPath(name).as_posix() != name:
            dst = os.path.sep.join(PureWindowsPath(name).parts)
            dst = os.path.join(grouptemp, dst)
            dstdir = os.path.dirname(dst)
            if dstdir:
              os.makedirs(dstdir, exist_ok=True)
            shutil.move(os.path.join(grouptemp, name), dst)
        # don't have a single top-level directory
        if len(os.listdir(grouptemp)) == 1:
          toplevel = grouptemp
          while len(os.listdir(toplevel)) == 1:
            nextlevel = os.path.join(toplevel, os.listdir(toplevel)[0])
            if not os.path.isdir(nextlevel):
              break
            toplevel = nextlevel
          if toplevel != grouptemp:
            with TemporaryDirectory() as tmptoplevel:
              # move everything within toplevel to a new temp dir
              for name in os.listdir(toplevel):
                shutil.move(os.path.join(toplevel, name), tmptoplevel)
              # clear rm -rf the single dir in grouptemp
              shutil.rmtree(os.path.join(grouptemp, os.listdir(grouptemp)[0]))
              # move everything back
              for name in os.listdir(tmptoplevel):
                shutil.move(os.path.join(tmptoplevel, name), grouptemp)
        # collect filenames
        # key is the dstname of the file, value is a list of src paths
        files = {}
        need_moved = deepcopy(include)
        for path in set(include.values()):
          if not os.path.isdir(os.path.join(grouptemp, path)):
            continue
          for name in os.listdir(os.path.join(grouptemp, path)):
            name = name.lower()
            for key in need_moved:
              if need_moved[key] != path:
                continue
              if key.match(name):
                del need_moved[key]
                break
        for dirpath, _, filenames in os.walk(grouptemp):
          for name in filenames:
            # compare files if name seen before (ignore identical files)
            outname = dstname(name)
            # a completely bad name will become empty
            if not outname:
              # replace a bad name with "badname"
              outname = 'badname'
            if outname in files:
              for other in files[outname]:
                if filecmp.cmp(other, os.path.join(dirpath,name),shallow=False):
                  break
              if filecmp.cmp(other,os.path.join(dirpath,name),shallow=False):
                logs.append(f'Group {group}, ' + \
                            f'ignoring duplicate file: \"{name}\"')
                continue
            # the name matches a path we want
            if dirpath == grouptemp and \
                  any(outname == path for path in set(need_moved.values())):
              outname += '.renamed'
              logs.append(f'Renaming: group {group} file {name} -> {outname}')
              shutil.move(os.path.join(dirpath, name),
                          os.path.join(dirpath, outname))
              name = outname
            # key is the dstname of the file, value is a list of src paths
            if outname not in files:
              files[outname] = []
            files[outname].append(os.path.join(dirpath, name))
        # for each filename to move into xpath
        for name in files:
          while len(files[name]) > 0:
            src = files[name].pop()
            # we want this file to go to a specific dir
            if name.lower() in need_moved:
              dst = os.path.join(xpath, need_moved[name.lower()], name)
            # put it in relative to the path it had
            else:
              # dirname without the group's temp prefix
              dst = os.path.dirname(src).removeprefix(grouptemp)
              # remove the lingering os.path.sep
              dst = dst.lstrip(os.path.sep)
              # remove any special chars in any of the path's parts
              dst = [dstname(part) for part in dst.split(os.path.sep)]
              # if any part became empty replace it with "badname"
              dst = [part if part else 'badname' for part in dst]
              # rejoin it with the path separator
              dst = os.path.sep.join(dst)
              # this goes into the group's final xpath
              dst = os.path.join(xpath, dst, name)
            # we could have a name collision
            if os.path.isfile(dst):
              # rename the file to a name that doesn't exist
              oldname = dst.split(xpath)[-1]
              # append a number to the file, beginning with 2
              dst = [dst, '2']
              while os.path.isfile('.'.join(dst)):
                dst[1] = str(int(dst[1])+1)
              dst = '.'.join(dst)
              # note that the file was renamed in the extraction log
              msg = f'Group {group} renamed {oldname} to {dst.split(xpath)[-1]}'
              logs.append(msg)
              # note that the file was renamed in the group's sub.nfo
              with open(f'{xpath}/sub.nfo','a') as outfile:
                outfile.write(msg+'\n')
            # ensure the path exists
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # move the src into the dst
            shutil.move(src, dst)
            # attempt dos2unix
            try:
              # universal newlines turns any newline into \n
              with open(dst, 'r') as infile:
                contents = infile.read()
              # ensure the file ends with a newline
              if contents[-1] != '\n':
                contents += '\n'
              with open(dst, 'w') as outfile:
                outfile.write(contents)
            # not a text file or something
            except:
              pass
      # end with grouptemp, move the zip into xpath
      shutil.move(zipname, f'{xpath}/group{group}.zip')
      # done with this group's zip
    logs.append('Extraction complete')
    return logs, err

  def extractphasezip(self,
                      phasedir: str,
                      phasezip: str,
                      keyfile: str,
                      groupre: str,
                      include: Dict[str,str],
                      exclude: List[str],
                      title: str='Extract Phase Dir') -> None:
    '''
    This is the base extraction method for a zip of zips

    The extraction log is stored in the output directory, ``phasedir``

      *If there was a prior extraction, prior decisions made can be repeated*

    Args:
      phasedir (str): The output directory for all group files
      phasezip (str): The filename of the zip of zips
      keyfile (str, Optional): A keyfile to aid association of filename->group
      groupre (str): Regex to use to associate filename->group
      include: (dict[str, str]):  Explicit map of files to destination
      exclude: (list[str]): patterns for files to not extract
      title: (str): The title for prompts
    '''
    logfile = os.path.join(phasedir, 'x.log')
    if not os.path.isfile(phasezip):
      self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNANY,
        title=title,
        body=['Cannot extract phasezip'],
        err=[f'Not a file: \"{phasezip}\"'],
      )
      return -1
    steps = []
    if os.path.isfile(logfile):
      with open(logfile, 'r') as infile:
        for line in infile.readlines():
          if line.startswith('*'):
            line = line.split()[0][1:]
            steps.append(line)
      if steps:
        _, _, c = self.scr.window(
          WinOpt.SHOWCURS|WinOpt.RETURNANY,
          title=title,
          err=[f'Extraction log \"{logfile}\" already exists'],
          footer='Repeat previous decisions? [Y/n] ',
        )
        if c in ('N', 'n'):
          steps = []
    if phasedir != os.getcwd() and \
        os.path.isdir(phasedir) and len(os.listdir(phasedir)) > 0:
      _, _, c = self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNANY,
        title=title,
        err=[f'Output directory {phasedir} already exists'],
        footer='Delete directory? [y/N] ',
      )
      if c not in ('Y', 'y'):
        return 1
      shutil.rmtree(phasedir)
    logs = []
    with TemporaryDirectory() as tempdir:
      try:
        with ZipFile(phasezip, 'r') as archive:
          archive.extractall(path=tempdir)
        logs, err = self.extract(tempdir, phasedir, keyfile,
                            groupre, include, exclude, steps)
      except Exception as e:
        self.scr.window(
          WinOpt.SHOWCURS|WinOpt.RETURNANY,
          title=title,
          body=[f'EXCEPTION opening/extracting: \"{phasezip}\"'],
          err=[m.strip() for m in re.split(r'[:\n]+',str(e))],
        )
        return
    if logs and os.path.isdir(os.path.dirname(logfile)):
      with open(logfile, 'w') as outfile:
        outfile.write('\n'.join(logs)+'\n')
      self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNKEY|WinOpt.TEXTBOX,
        title=title,
        body=['Phasezip extracted successfully'],
        choices=logs,
        err=err,
        footer='Press enter to continue . . . ',
      )
    else:
      self.scr.window(
        WinOpt.SHOWCURS|WinOpt.RETURNKEY|WinOpt.TEXTBOX,
        title=title,
        body=['Extraction not successful'],
        choices=logs,
        err=err,
        footer='Press enter to continue . . . ',
      )
