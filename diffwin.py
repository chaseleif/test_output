#! /usr/bin/env python3

import curses, os, re, sys
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

  Alternate usage, instantiating a class, is win = DiffWindow()
    ** Using the context manager is safer as it ensures curses is cleaned up **
    (the method which initializes curses is initscr)
    (the method which restores the shell is stopscr)
    initscr will be called automatically when needed
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

    The intended usage is as described above and in the "if name == __main__"
  '''
  def __init__(self, ltitle='left', rtitle='right'):
    self.ltitle = ltitle
    self.rtitle = rtitle

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
    # this will be background / border
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
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
      self.initscr()
    # remove empty lines, trailing whitespace, and tabs from lhs / rhs
    lhs = [re.sub('\t','  ',line.rstrip()) for line in lhs \
                                              if line.strip() != '']
    rhs = [re.sub('\t','  ',line.rstrip()) for line in rhs \
                                              if line.strip() != '']
    # get column length for lhs and rhs (max of any element)
    self.lwidth = max([len(row) for row in lhs])
    self.rwidth = max([len(row) for row in rhs])
    # track the height/width
    height, width = self.stdscr.getmaxyx()
    # track top left 'coordinate' of the text in the lists
    # the l/rpos is the starting row + col to display
    # we start with injected input KEY_HOME, so row is set in conditions below
    lpos = [123,0] # lpos[0] is starting row
    rpos = [456,0] # rpos[1] is starting col
    # set limits for pos
    # don't set pos row less then -height
    # don't set pos col less than -4 (allows 3 digit num)
    # 1 row remains on screen (at bottom)
    minpos = [-height+1, -4]
    # max pos prints 1 row of a pane (at top), right col of line
    maxlpos = [len(lhs)-1, self.lwidth-1]
    maxrpos = [len(rhs)-1, self.rwidth-1]
    # allow independent scrolling, default is locked left/right
    singlescroll = False
    # side toggle for independent scrolling, defaults to left side
    leftscroll = True
    # whether we could scroll a side
    scroll = lambda side: not singlescroll or \
                    (leftscroll if side=='left' else not leftscroll)
    # whether the given scroll key will cause a scroll
    # if not then we don't need to needlessly repaint
    # move toward
    #  max/min pos[0] (up/down) or pos[1] (left/right)
    willscroll = lambda key: \
                        ((key == curses.KEY_HOME or \
                          key == curses.KEY_PPAGE or \
                          key == curses.KEY_UP) and \
                  (scroll('left') and lpos[0] > minpos[0]) or \
                  (scroll('right') and rpos[0] > minpos[0])) or \
                        ((key == curses.KEY_END or \
                          key == curses.KEY_NPAGE or \
                          key == curses.KEY_DOWN) and \
                  (scroll('left') and lpos[0] < maxlpos[0]) or \
                  (scroll('right') and rpos[0] < maxrpos[0])) or \
                        (key == curses.KEY_LEFT and \
                  (scroll('left') and lpos[1] > minpos[1]) or \
                  (scroll('right') and rpos[1] > minpos[1])) or \
                        (key == curses.KEY_RIGHT and \
                  (scroll('left') and lpos[1] < maxlpos[1]) or \
                  (scroll('right') and rpos[1] < maxrpos[1]))
    # toggle for whether to highlight matching lines
    highlight = True
    # toggle for whether to print line numbers
    linenums = True
    # shift amount for pane boundary, division between lhs/rhs views
    paneshmt = 0
    # we'll start at home
    ch = curses.KEY_HOME
    # NOTE: we start at HOME to set the start row and trigger paint
    # these chars will quit: escape = 27, 'Q'=81, 'q'=113
    while ch not in [27, 81, 113]:
      # do keys that won't trigger repainting first
      # the space key toggles independent scrolling
      if ch == 32:
        singlescroll = not singlescroll
      # the tab key toggles whether lhs is active (otherwise rhs)
      elif ch == 9:
        leftscroll = not leftscroll
      # otherwise we will repaint unless next list doesn't match
      else:
        repaint = True
      # repaint the screen if we do one of these conditions
      # a resize event
      if ch == curses.KEY_RESIZE:
        height, width = self.stdscr.getmaxyx()
        minpos[0] = -height+1
        # ensure we didn't go past minpos
        if lpos[0] < minpos[0]:
          lpos[0] = minpos[0]
        if rpos[0] < minpos[0]:
          rpos[0] = minpos[0]
      # toggle line match highlight with [dDhH] (for diff/highlight)
      elif ch in [68, 72, 100, 104]:
        highlight = not highlight
      # toggle printing line numbers with [nN]
      elif ch in [78, 110]:
        linenums = not linenums
      # plus key to shift pane separator right
      elif ch == 43 and width//2+paneshmt < width-2:
        paneshmt += 1
      # minus key to shift pane separator left
      elif ch == 45 and width//2+paneshmt > 0:
        paneshmt -= 1
      # equal key to reset pane shift
      elif ch == 61 and paneshmt != 0:
        paneshmt = 0
      elif willscroll(ch):
        # go to top
        if ch == curses.KEY_HOME:
          # first, set pos to -2 (top is title+start+firstline)
          # on a second press move top line to bottom of screen
          if scroll('left'):
            if lpos[0] > -2:
              lpos[0] = -2
            else:
              lpos[0] = minpos[0]
          if scroll('right'):
            if rpos[0] > -2:
              rpos[0] = -2
            else:
              rpos[0] = minpos[0]
        # go to the bottom
        elif ch == curses.KEY_END:
          # first, fill height with bottom of text
          # on a second press move bottom line to top of screen
          if scroll('left'):
            if lpos[0] < len(lhs) - height + 1:
              lpos[0] = len(lhs) - height + 1
            else:
              lpos[0] = maxlpos[0]
          if scroll('right'):
            if rpos[0] < len(rhs) - height + 1:
              rpos[0] = len(rhs) - height + 1
            else:
              rpos[0] = maxrpos[0]
        # page up
        elif ch == curses.KEY_PPAGE:
          if scroll('left'):
            lpos[0] = max(lpos[0]-height-3, minpos[0])
          if scroll('right'):
            rpos[0] = max(rpos[0]-height-3, minpos[0])
        # page down
        elif ch == curses.KEY_NPAGE:
          if scroll('left') and height < len(lhs):
            lpos[0] = min(lpos[0]+height-3, maxlpos[0])
          if scroll('right') and height < len(rhs):
            rpos[0] = min(rpos[0]+height-3, maxrpos[0])
        # scroll up
        elif ch == curses.KEY_UP:
          if scroll('left') and lpos[0] > minpos[0]:
            lpos[0] -= 1
          if scroll('right') and rpos[0] > minpos[0]:
            rpos[0] -= 1
        # scroll down
        elif ch == curses.KEY_DOWN:
          if scroll('left') and lpos[0] < maxlpos[0]:
            lpos[0] += 1
          if scroll('right') and rpos[0] < maxrpos[0]:
            rpos[0] += 1
        # scroll left
        elif ch == curses.KEY_LEFT:
          if scroll('left') and lpos[1] > minpos[1]:
            lpos[1] -= 1
          if scroll('right') and rpos[1] > minpos[1]:
            rpos[1] -= 1
        # scroll right
        elif ch == curses.KEY_RIGHT:
          if scroll('left') and lpos[1] < maxlpos[1]:
            lpos[1] += 1
          if scroll('right') and rpos[1] < maxrpos[1]:
            rpos[1] += 1
      # if we didn't change the pos then don't repaint
      else:
        repaint = False
      if repaint:
        drawsplitpane(self.stdscr, lhs, lpos, rhs, rpos,
                    highlight, paneshmt,
                    self.ltitle, self.rtitle, linenums)
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
                  '     Toggle line-number printing:  n, N',
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
      self.initscr()
    # the title for each window
    title = 'DiffWindow - a Python curses script to compare 2 text files'
    # the body text
    body = [['Choose an option from the menu below:']]
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
          self.ltitle = name
          choices[legend.index('lhs')] += ' (set to \"' + self.ltitle + '\")'
        # had a filename and don't have one now, remove filename
        elif lhs is not None and ret is None:
          self.ltitle = 'left'
          choices[legend.index('lhs')] = \
              choices[legend.index('lhs')].split(' (set to ')[0]
        # had a filename before and (may) have a different one now
        else:
          self.ltitle = name
          choices[legend.index('lhs')] = \
              choices[legend.index('lhs')].split(' (set to ')[0]
          choices[legend.index('lhs')] += ' (set to \"' + self.ltitle + '\")'
        lhs = ret
      # open a file to set rhs
      elif legend[ch] == 'rhs':
        ret, name = filemenu(self.stdscr, title=title)
        # didn't have a rhs before and didn't get one
        if rhs is None and ret is None: pass
        # didn't have a rhs before and have one now
        elif rhs is None and ret is not None:
          self.rtitle = name
          choices[legend.index('rhs')] += ' (set to \"' + self.rtitle + '\")'
        # had a filename and don't have one now, remove filename
        elif rhs is not None and ret is None:
          self.rtitle = 'right'
          choices[legend.index('rhs')] = \
              choices[legend.index('rhs')].split(' (set to ')[0]
        # had a filename before and (may) have a different one now
        else:
          self.rtitle = name
          choices[legend.index('rhs')] = \
              choices[legend.index('rhs')].split(' (set to ')[0]
          choices[legend.index('rhs')] += ' (set to \"' + self.rtitle + '\")'
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
          ltitle = self.ltitle
          rtitle = self.rtitle
          self.ltitle = os.path.basename(ltitle)
          self.rtitle = os.path.basename(rtitle)
          if self.ltitle == self.rtitle:
            self.ltitle = f'a/{self.ltitle}'
            self.rtitle = f'b/{self.rtitle}'
          self.showdiff(lhs, rhs)
          self.ltitle = ltitle
          self.rtitle = rtitle
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
    ltitle, rtitle = sys.argv[1], sys.argv[2]
    with open(ltitle,'r') as infile: lhs = infile.readlines()
    with open(rtitle,'r') as infile: rhs = infile.readlines()
    ltitle = os.path.basename(ltitle)
    rtitle = os.path.basename(rtitle)
    if ltitle == rtitle:
      ltitle = f'a/{ltitle}'
      rtitle = f'b/{rtitle}'
    with DiffWindow(ltitle, rtitle) as win:
      win.showdiff(lhs, rhs)
  else:
    with DiffWindow() as win:
      win.mainmenu()
  # class usage
  '''
    If curses is not cleaned up properly
    You may be left with an unusable terminal
    You must call win.stopscr()
      or the win object must be deleted, this also calls stopscr
      deleting the object can be done manually, with del
  '''
  #win = DiffWindow()
  #win.initscr() # optional, called automatically in showdiff
  #win.showdiff(lhs, rhs)
  #win.stopscr() # called in del if initscr has been called

# vim: tabstop=2 shiftwidth=2 expandtab
