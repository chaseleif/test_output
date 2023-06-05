#! /usr/bin/env python3

import curses, re, sys
sys.dont_write_bytecode = True
from cursemenu import showmenu, filemenu, drawsplitpane
sys.dont_write_bytecode = False

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

'''
  DiffWindow
  ___________
  An implementation of curses for side-by-side file comparison

  A class to be used in the manner "with DiffWindow() as win:"
    this usage keeps curses from messing up the terminal on exceptions/etc.

  Alternate usage, instantiating a class, is win = DiffWindow(unsafe=True)
    (the method which initializes curses is initscr)
    (the method which restores the shell is stopscr)
    initscr will be called automatically when needed if unsafe=True
    stopscr will be called on __del__

  The "main" method, showdiff, takes 2 lists of strings like:
    lhs = [line.rstrip() for line in lhsfile.readlines()]
    rhs = [line.rstrip() for line in rhsfile.readlines()]

  Alternatively, this script can run as a menu-driven script:
    with DiffWindow() as win:
      win.mainmenu()
  ___________
  Normal navigation keys allow scrolling:
    up, down, left, right, pgup, pgdown, home, end
  ___________
  Normal exit is by one of: escape, q, or Q
  ___________
  Default mode: both sides scroll together and matches highlighted
  ___________
  The 'space' key toggles independent/locked scrolling
  The 'tab' key switches between lhs/rhs for independent scrolling
  The '+' and '-' keys (plus/minus) will shift the pane separator left/right
  The '=' key will reset the pane shift
  The keys d, D, h, or H toggle match highlighting
    (d for diff, h for highlight)
  When highlighting is enabled lhs/rhs lines that are the same
    **and are on the same level of the screen**
    will be highlighted
'''

class DiffWindow:
  '''
  __init__

    Set unsafe flag to allow usage without enter/exit
    The intended usage is as described above and in the "if name == __main__"
  '''
  def __init__(self, unsafe=False): self.unsafe = unsafe

  '''
  __enter__

    We init curses, get a screen, and set options
    Returns self for use with the listdiff() function
  '''
  def __enter__(self): return self.initscr()

  '''
  __exit__

    We teardown curses and return the terminal to normal operation
  '''
  def __exit__(self, type, value, traceback): self.stopscr()

  '''
  __del__

    Ensure curses has been town down
  '''
  def __del__(self):
    try:
      if self.havescr: self.stopscr()
    except AttributeError: pass

  '''
  initscr

    The actual init function to init curses and set vars
  '''
  def initscr(self):
    # flag init
    try:
      if self.havescr: return
    except AttributeError: pass
    self.havescr = True
    # get the std screen
    self.stdscr = curses.initscr()
    # enable color output
    curses.start_color()
    # we can use pair numbers from 1 ... (0 is standard)
    # COLOR_ BLACK, BLUE, CYAN, GREEN, MAGENTA, RED, WHITE, YELLOW
    # this will be for standard text
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    # this will be for title text
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    # this will be error text
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    # suppress echo of keypresses
    curses.noecho()
    # immediately respond to keypresses
    curses.cbreak()
    # hide the cursor
    curses.curs_set(0)
    # enable to cursor to go out of bounds
    self.stdscr.scrollok(True)
    # enable use of curses info for curses.KEY_LEFT, etc.
    self.stdscr.keypad(True)
    return self

  '''
  stopscr

    The actual stop method to teardown the curses
  '''
  def stopscr(self):
    # reset modes back to normal
    try:
      if self.havescr:
        self.havescr = False
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()
    except AttributeError: pass

  '''
  showdiff(lhs, rhs)

    This is the main driver function for the file diff display
    Takes 2 lists of strings, lhs and rhs

    Returns when the escape, q, or Q key has been pressed
  '''
  def showdiff(self, lhs=[], rhs=[]):
    # confirm class usage
    try:
      if not self.havescr: self.initscr()
    except AttributeError:
      if self.unsafe: self.initscr()
      else:
        raise AssertionError('unsafe is not true and curses not initialized')
    # remove empty lines, trailing whitespace, and tabs from lhs / rhs
    lhs = [re.sub('\t','  ',line.rstrip()) for line in lhs \
                                              if line.strip() != '']
    rhs = [re.sub('\t','  ',line.rstrip()) for line in rhs \
                                              if line.strip() != '']
    # get column length for lhs and rhs (max of any element)
    self.lwidth = 0
    for row in lhs: self.lwidth = max(len(row),self.lwidth)
    self.rwidth = 0
    for row in rhs: self.rwidth = max(len(row),self.rwidth)
    # track top left 'coordinate' of the text in the lists
    # the l/rpos is the starting row + col to display
    lpos = [0,0] # lpos[0] is starting row
    rpos = [0,0] # rpos[1] is starting col
    # track the last known height/width as the window could be resized
    lastheight, lastwidth = self.stdscr.getmaxyx()
    # allow independent scrolling
    singlescroll = False
    # side toggle for independent scrolling
    leftscroll = True
    scroll = lambda x: not singlescroll or leftscroll if x=='left' \
                    else not singlescroll or not leftscroll
    # toggle for whether to highlight matching lines
    highlight = True
    # shift amount for pane boundary, division between lhs/rhs views
    paneshmt = 0
    # these chars will quit: escape = 27, 'Q'=81, 'q'=113
    # we'll start at home
    ch = curses.KEY_HOME
    while ch not in [27, 81, 113]:
      middle = lastwidth//2 + paneshmt
      # repaint the screen if we do one of these conditions
      repaint = True
      # the space key to toggle independent scrolling
      if ch == 32: singlescroll = not singlescroll
      # the tab key to toggle whether lhs is active (otherwise rhs)
      elif ch == 9: leftscroll = not leftscroll
      # toggle line match highlight with d, D, h, or H (for diff/highlight)
      elif ch in [68, 72, 100, 104]: highlight = not highlight
      # plus key to shift pane separator right
      elif ch == 43:
        if middle < lastwidth - 2: paneshmt += 1
      # minus key to shift pane separator left
      elif ch == 45:
        if middle > 2: paneshmt -= 1
      # equal key to reset pane shift
      elif ch == 61: paneshmt = 0
      # reset positions
      elif ch == curses.KEY_HOME:
        if scroll('left'): lpos[0] = -1
        if scroll('right'): rpos[0] = -1
      # go to the bottom
      elif ch == curses.KEY_END:
        # fit our maxheight in the last known height
        if scroll('left') and lastheight < len(lhs):
          lpos[0] = len(lhs) - lastheight + 1
        if scroll('right') and lastheight < len(rhs):
          rpos[0] = len(rhs) - lastheight + 1
      # page up
      elif ch == curses.KEY_PPAGE:
        if scroll('left'):
          lpos[0] -= lastheight - 4
          if lpos[0] < 0: lpos[0] = -1
        if scroll('right'):
          rpos[0] -= lastheight - 4
          if rpos[0] < 0: rpos[0] = -1
      # page down
      elif ch == curses.KEY_NPAGE:
        if scroll('left') and lastheight < len(lhs):
          lpos[0] += lastheight - 4
          if lpos[0] > len(lhs) - lastheight:
            lpos[0] = len(lhs) - lastheight + 1
        if scroll('right') and lastheight < len(rhs):
          rpos[0] += lastheight - 4
          if rpos[0] > len(rhs) - lastheight:
            rpos[0] = len(rhs) - lastheight + 1
      # scroll up
      elif ch == curses.KEY_UP:
        if scroll('left'): lpos[0] -= 1
        if scroll('right'): rpos[0] -= 1
      # scroll down
      elif ch == curses.KEY_DOWN:
        if scroll('left'): lpos[0] += 1
        if scroll('right'): rpos[0] += 1
      # scroll left
      elif ch == curses.KEY_LEFT:
        if scroll('left') and lpos[1] > 0:
          lpos[1] -= 1
        if scroll('right') and rpos[1] > 0:
          rpos[1] -= 1
      # scroll right
      elif ch == curses.KEY_RIGHT:
        if scroll('left') and middle > 2:
          if self.lwidth - lpos[1] > middle - 2: lpos[1] += 1
        if scroll('right') and middle < lastwidth:
          if self.rwidth - rpos[1] > lastwidth - middle - 2: rpos[1] += 1
      # if we didn't change the pos then don't repaint
      else: repaint = False
      if repaint:
        lastheight, lastwidth = drawsplitpane(self.stdscr,
                                              lhs, lpos, rhs, rpos,
                                              highlight, paneshmt)
      ch = self.stdscr.getch()

  '''
  commands()

    Print command information
  '''
  def commands(self, title=''):
    controls = [['Commands available while the diff view is active:'],
                 ['                            Quit:  escape, q, Q',
                  '       Toggle match highlighting:  d, D, h, H',
                  '     Toggle left/right pane lock:  space',
                  'Toggle left/right pane scrolling:  tab',
                  '  Move pane separator left/right:  +/-',
                  '      Reset pane separator shift:  =']]
    choices = ['Press the any key to return to the main menu . . . ']
    showmenu(self.stdscr, title=title, body=controls,
              choices=choices, infobox=True, curs=2)

  '''
  mainmenu()

    This is the main menu for the menu-driven interface
  '''
  def mainmenu(self):
    # confirm class usage
    try:
      if not self.havescr: self.initscr()
    except AttributeError:
      if self.unsafe: self.initscr()
      else:
        raise AssertionError('unsafe is not true and curses not initialized')
    # the title for each window
    title = 'DiffWindow - a Python curses script to compare 2 text files'
    # the body text
    body = [['Copyright (C) 2023 Chase Phelps',
              'Licensed under the GNU GPL v3 license'],
            ['Choose an option from the menu below:']]
    # the choices
    choices = ['Select the left-hand side file',
                'Select the right-hand side file',
                'Show the diff between the files',
                'Show available commands for diff view',
                'Quit']
    # a legend of choices to allow more descriptive comparison
    legend = ['lhs','rhs','diff','commands','quit']
    # initialize our variables
    ch = 0
    error = None
    lhs, rhs = None, None
    # while quit is not chosen
    while True:
      # get a choice
      topline, ch = showmenu(self.stdscr, title=title, body=body,
                              err=error, choices=choices, hpos=ch)
      # allow to quit on escape, q, or Q:
      if ch is None: break
      error=None
      # open a file to set lhs
      if legend[ch] == 'lhs':
        ret, name = filemenu(self.stdscr, title=title)
        # didn't have a lhs before and didn't get one
        if lhs is None and ret is None: pass
        # didn't have a lhs before and have one now
        elif lhs is None and ret is not None:
          choices[legend.index('lhs')] += ' (set to \"' + name + '\")'
        # had a filename and don't have one now, remove filename
        elif lhs is not None and ret is None:
          choices[legend.index('lhs')] = \
              choices[legend.index('lhs')].split(' (set to ')[0]
        # had a filename before and (may) have a different one now
        else:
          choices[legend.index('lhs')] = \
              choices[legend.index('lhs')].split(' (set to ')[0]
          choices[legend.index('lhs')] += ' (set to \"' + name + '\")'
        lhs = ret
      # open a file to set rhs
      elif legend[ch] == 'rhs':
        ret, name = filemenu(self.stdscr, title=title)
        # didn't have a rhs before and didn't get one
        if rhs is None and ret is None: pass
        # didn't have a rhs before and have one now
        elif rhs is None and ret is not None:
          choices[legend.index('rhs')] += ' (set to \"' + name + '\")'
        # had a filename and don't have one now, remove filename
        elif rhs is not None and ret is None:
          choices[legend.index('rhs')] = \
              choices[legend.index('rhs')].split(' (set to ')[0]
        # had a filename before and (may) have a different one now
        else:
          choices[legend.index('rhs')] = \
              choices[legend.index('rhs')].split(' (set to ')[0]
          choices[legend.index('rhs')] += ' (set to \"' + name + '\")'
        rhs = ret
      # show the diff of lhs and rhs
      elif legend[ch] == 'diff':
        if not lhs and not rhs:
          error = 'Left- and Right- side files must be selected first!'
        elif not lhs:
          error = 'Left- side file must be selected first!'
        elif not rhs:
          error = 'Right- side file must be selected first!'
        else:
          self.showdiff(lhs, rhs)
      # show the command information
      elif legend[ch] == 'commands':
        self.commands(title=title)
      # quit
      elif legend[ch] == 'quit':
        return

'''
__name__ == __main__
  When len(argv) == 3, attempt to read -> lhs=argv[1], rhs=argv[2]
  Otherwise start the main menu

  Usage of DiffWin class is demonstrated below
'''
if __name__ == '__main__':
  if len(sys.argv) == 3:
    lhs, rhs = [], []
    with open(sys.argv[1]) as infile: lhs = infile.readlines()
    with open(sys.argv[2]) as infile: rhs = infile.readlines()
    with DiffWindow() as win: win.showdiff(lhs, rhs)
  else:
    with DiffWindow() as win: win.mainmenu()
  # class usage
  #win = DiffWindow(unsafe=True)
  #win.initscr() # optional, called automatically in showdiff if unsafe=True
  #win.showdiff(lhs, rhs)
  #win.stopscr() # called in del if initscr has been called

# vim: tabstop=2 shiftwidth=2 expandtab
