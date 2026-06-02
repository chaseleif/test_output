import curses, os, re, sys
from inspect import getdoc
from pathlib import Path
from types import TracebackType
from typing import List, Optional, Tuple, Type, Union
from .utils import removecommonprefix
from .win import CursesScreen, WinOpt

'''
    DiffWindow - a Python script to view difference between 2 text files
    Copyright (C) 2023  Chase Phelps

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

DiffArgs = Tuple[str, str, List[str], str, List[str]]

class DiffWindow:
  '''
  A window that displays a side-by-side diff of two files for comparison
  '''
  def __init__(self, argv: Optional[Union[List[str], DiffArgs]]=None) -> None:
    '''
    Initialize the DiffWindow

    When given arguments
      - argv=[program, leftfile, rightfile]
      - argv=(title, ltitle, lhs, rtitle, rhs)

    Will setup, call ``diffwindow``, and cleanup

    Args:
      argv: (Optional[Union[List[str], Diffargs]]): Optional arguments
    '''
    # the title for each window
    self.title = 'DiffWindow - a driver utility from CSTester'
    self.ltitle, self.rtitle = 'left', 'right'
    self.lhs, self.rhs = [], []
    self.scr = CursesScreen()
    if argv is None:
      pass
    elif len(argv) == 3:
      try:
        with open(argv[1], 'r') as infile:
          lhs = infile.readlines()
        with open(argv[2], 'r') as infile:
          rhs = infile.readlines()
        if lhs and rhs:
          self.ltitle = argv[1]
          self.rtitle = argv[2]
          ltitle, rtitle=removecommonprefix(self.ltitle, self.rtitle)
          try:
            self.scr.initscr()
            self.scr.diffwindow((self.title, ltitle, lhs, rtitle, rhs))
          finally:
            self.scr.cleanup()
            self.scr = None
      except Exception as e:
        print(self.title)
        print()
        print('Arguments provided but unable to open files')
        print(f'Exception: {e}')
        self.ltitle, self.rtitle = 'left', 'right'
    # called from another script with diffwindow args
    elif isinstance(argv, tuple) and len(argv) == 5:
      try:
        self.scr.initscr()
        self.scr.diffwindow(argv)
      finally:
        self.scr.cleanup()
        self.scr = None

  def __enter__(self) -> 'DiffWindow':
    if self.scr is not None:
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

  def help_mainmenu(self, title: str='') -> None:
    '''
    Display an informational window with the main menu help
    '''
    self.scr.window(WinOpt.RETURNKEY|WinOpt.TEXTBOX,
                    title=f'{title} Help',
                    choices=getdoc(self.mainmenu).strip('\n').split('\n'))

  def mainmenu(self) -> None:
    '''
    Show the diff view and provide navigation/commands for comparison

    The view compares lines with leading/trailing whitespace stripped,
    converts tabs to spaces, highlights matching lines,
    and can show line numbers.

    Open help while in the 'diff view' for a command listing
    '''
    # the body text
    body = ['Choose an option from the menu below:', '']
    # the choices
    opts = {'lhs':'Select the left-hand side file',
            'rhs':'Select the right-hand side file',
            'diff':'Show the diff between the files',
            'quit':'Quit'
            }
    keys = list(opts.keys())
    values = list(opts.values())
    helpkeys = ['?']
    hpos = 0
    # while quit is not chosen
    while True:
      disabled = [] if self.lhs and self.rhs else [keys.index('diff')]
      top, hpos, c = self.scr.window(WinOpt.RETURNKEY|WinOpt.RETURNDEL|WinOpt.USEHELP,
                                      title=self.title, body=body,
                                      disabled=disabled,
                                      choices=values, hpos=hpos)
      # delete key
      if c == 'KEY_DC':
        if keys[hpos] in ['lhs','rhs']:
          if getattr(self, keys[hpos]):
            setattr(self, keys[hpos], [])
            setattr(self,
                    'ltitle' if keys[hpos] == 'lhs' else 'rtitle',
                    'left' if keys[hpos] == 'lhs' else 'right')
            values[keys.index(keys[hpos])] = \
              values[keys.index(keys[hpos])].split(' (set to ')[0]
      # allow to quit on escape or quit
      elif c in CursesScreen.cancelkeys:
        break
      elif keys[hpos] == 'diff':
        ltitle, rtitle = removecommonprefix(self.ltitle, self.rtitle)
        self.scr.diffwindow((self.title, ltitle, self.lhs, rtitle, self.rhs))
      # set lhs/rhs
      elif keys[hpos] in ['lhs', 'rhs']:
        name = self.scr.getfile(self.title)
        if name is None:
          pass
        elif os.path.getsize(name) == 0:
          self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                              title=self.title,
                              err=[f'File {os.path.basename(name)} empty'])
        else:
          with open(name,'r') as infile:
            setattr(self, keys[hpos], infile.readlines())
          setattr(self, 'ltitle' if keys[hpos] == 'lhs' else 'rtitle', name)
          values[keys.index(keys[hpos])] = \
              values[keys.index(keys[hpos])].split(' (set to ')[0] + \
                f' (set to \"{name}\")'
