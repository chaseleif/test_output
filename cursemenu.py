#! /usr/bin/env python3

import curses, os, sys, termios, tty
from pathlib import Path

'''
    CurseMenu - a Python script providing some curses menu functions
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
modalwindow(scr, title, body, err, curs, confirm)

  This method pops up a modal window for information or error messages

  If there is a title, it is printed followed by a newline

  if err, err can be a single string or a list of strings
  If lines are within error, they are printed followed by a newline

  if body, it is a list of lists with strings
  if lines are within body, they are printed followed by a newline

  curses.curs_set is set with curs
    0 is hidden
    1 is (possibly) an underscore/line
    2 is (possibly) a block

  confirm is a list of accepting keypresses
  if confirm is empty then any return from getch is accepting

  the accepting result of getch is returned from this function
'''
def modalwindow(scr, title='', body=[[]], err=[], curs=0, confirm=[]):
  maxwidth = max(len(title), max(len(l) for s in body for l in s))
  if isinstance(err, str):
    maxwidth = max(maxwidth,len(err))
  elif err:
    maxwidth = max(maxwidth, max(len(e) for e in err))
  # set colors to be used
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  errorcolor = curses.color_pair(3) | curses.A_BOLD
  # get the dimensions
  height, width = scr.getmaxyx()
  # get side buffer
  lshift = (width-maxwidth)//2
  if lshift < 0:
    lshift = 0
  while True:
    # clear the screen
    scr.erase()
    # track the line number we are printing to
    linenum = 0
    # add the title
    if title:
      scr.insstr(linenum, (width-len(title))//2, title, titlecolor)
    # print all lines in a section of the body
    cursorcol = len(title)
    # print an error message if we have one
    if err:
      linenum += 1
      if err:
        if type(err) is list:
          for e in err:
            if e:
              linenum += 1
              if linenum >= height: break
              scr.insstr(linenum, lshift, e, errorcolor)
              cursorcol = len(e)
        else:
          linenum += 1
          if linenum < height:
            scr.insstr(linenum, lshift, err, errorcolor)
            cursorcol = len(err)
    if body:
      linenum += 1
      for section in body:
        linenum += 1
        for line in section:
          linenum += 1
          if line:
            if linenum >= height: break
            scr.insstr(linenum, lshift, line, itemcolor)
            cursorcol = len(line)
    # set the cursor according to the argument and refresh the screen
    if curs != 0:
      cursorcol += lshift
      if linenum < height and cursorcol < width:
        scr.move(linenum, cursorcol)
        curses.curs_set(curs)
    scr.refresh()
    # while we don't need to redraw the screen
    while True:
      # get our response, reset the cursor and process the response
      ch = scr.getch()
      curses.curs_set(0)
      if ch == curses.KEY_RESIZE:
        # get new dimensions and redraw
        height, width = scr.getmaxyx()
        lshift = (width-maxwidth)//2
        if lshift < 0:
          lshift = 0
        break
      # accept anything
      if not confirm:
        return ch
      # accept something in confirm
      elif ch in confirm:
        return ch

'''
getinputmenu(scr, title, prompt)
'''
def getinputmenu(scr, title='', prompt='Enter input:'):
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  val = ''
  fd = sys.stdin.fileno()
  oldfd = termios.tcgetattr(fd)
  height, width = scr.getmaxyx()
  try:
    while True:
      scr.erase()
      lpos = (width-len(title))//2
      if lpos < 0:
        lpos = 0
      scr.insstr(0, lpos, title, titlecolor)
      lpos = (width-len(prompt))//2
      if lpos < 0:
        lpos = 0
      scr.insstr(2, lpos, prompt, itemcolor)
      if val:
        line = 4
        lpos = (width-len(val))//2
        if lpos < 0:
          lpos = 0
        scr.insstr(4, lpos, val[:width], itemcolor)
        lpos += len(val)
        line = 4
        consumed = 0
        while lpos >= width:
          consumed += width
          line += 1
          scr.insstr(line, 0, val[consumed:consumed+width], itemcolor)
          lpos -= width
        scr.move(line, lpos)
      else:
        scr.move(4, width//2)
      curses.curs_set(2)
      scr.refresh()
      ret = False
      while True:
        ch = scr.get_wch()
        if ch == curses.KEY_RESIZE:
          height, width = scr.getmaxyx()
          break
        if ch in [curses.KEY_ENTER, 10, 13, '\n', '\r']:
          return val if val else None
        if ch in [curses.KEY_BACKSPACE, '\b', 127, '\x7f']:
          if val:
            val = val[:-1]
            break
        if isinstance(ch, str):
          val += ch
          break
      if ret:
        break
  finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, oldfd)

'''
choicemenu(scr, title, body, choices, infobox, curs, hpos)

  This method is used to print a text menu using the screen scr

  The title is drawn on the first line
  An empty line separates the title from the body
  The body is a list of lists of strings
  Each is separated by a line

  The remaining lines are "choice" lines which can be scrolled
  The current selection at hpos will be highlighted
  Empty strings can be used and are skipped when scrolling:
    Choosable lines must not be empty
    The first and last line of choices must not be empty strings
    Two choice lines may have a single empty string between them
    (empty strings shouldn't be adjacent in choices)

  The user makes their selection with navigation keys
  When enter is pressed, the corresponding index of choices is returned
  If escape, q, or Q is pressed, None is returned

  curses.curs_set is set with the curs parameter
    0 is hidden
    1 is (possibly) an underscore/line
    2 is (possibly) a block
'''
def choicemenu(scr,
              title='', body=[[]], choices=[],
              curs=0, topline=0, hpos=0):
  if hpos < topline: hpos = topline
  # track width to center text
  try:
    maxwidth = max(len(title), max(len(l) for s in body for l in s))
  # nothing in the body
  except ValueError:
    maxwidth = len(title)
  maxwidth = max(maxwidth, max(len(c) for c in choices))
  # set colors to be used
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  activecolor = curses.color_pair(1) | curses.A_BOLD
  # get the dimensions
  height, width = scr.getmaxyx()
  # get side buffer
  lshift = (width-maxwidth)//2
  if lshift < 0:
    lshift = 0
  # toplines include the title and body, these are before the choices
  choicestart = 2 + len(body) + sum([len(s) for s in body])
  while True:
    # clear the screen
    scr.erase()
    # add the title
    lpos = (width-len(title))//2
    if lpos < 0:
      lpos = 0
    scr.insstr(0, lpos, title, titlecolor)
    # track the line number we are printing to
    linenum = 1
    for section in body:
      # print all lines in a section of the body
      for line in section:
        linenum += 1
        if linenum >= height: break
        scr.insstr(linenum, lshift, line, itemcolor)
      # separate body sections by a newline
      linenum += 1
    # separate body from remainder with another newline
    linenum += 1
    # i is zero indexed matching hpos
    for i, line in enumerate(choices[topline:]):
      # we cannot go beyond height if choices is a long list
      if linenum >= height: break
      # set the color to active if this is our highlight position
      color = activecolor if i+topline == hpos else itemcolor
      scr.insstr(linenum, lshift, line, color)
      linenum += 1
    # set the cursor according to the argument and refresh the screen
    if curs != 0:
      cursorcol = lshift + len(choices[hpos])
      if cursorcol < width:
        scr.move(choicestart + hpos - topline, cursorcol)
        curses.curs_set(curs)
    scr.refresh()
    # while we don't need to redraw the screen
    ch = -1
    while ch not in (curses.KEY_HOME, curses.KEY_END, curses.KEY_UP,
                    curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE,
                    curses.KEY_RESIZE):
      # get our response, reset the cursor and process the response
      ch = scr.getch()
      curses.curs_set(0)
      # on enter we return our highlighted position
      if ch in [curses.KEY_ENTER, 10, 13]: return topline, hpos
      # allow to return without making a selection with escape or q
      if ch in [27, 81, 113]: return None, None
      # go to the top
      if ch == curses.KEY_HOME:
        hpos = 0
        topline = 0
      # go to the bottom
      elif ch == curses.KEY_END and choicestart + len(choices) > height:
        hpos = len(choices) - 1
      # go up
      elif ch == curses.KEY_UP and hpos > 0:
        hpos -= 1
        if not choices[hpos]:
          hpos -= 1
      # go down
      elif ch == curses.KEY_DOWN and hpos < len(choices) - 1:
        hpos += 1
        # skip over blank lines
        if not choices[hpos]:
          hpos += 1
      # jump up
      elif ch == curses.KEY_PPAGE and hpos > 0:
        hpos -= 4
        if hpos < 0:
          hpos = 0
          topline = 0
        if not choices[hpos]:
          hpos -= 1
      # jump down
      elif ch == curses.KEY_NPAGE and hpos < len(choices) - 1:
        hpos += 4
        if hpos >= len(choices) - 1: hpos = len(choices) - 1
        if not choices[hpos]:
          hpos += 1
      elif ch == curses.KEY_RESIZE:
        # get new dimensions
        height, width = scr.getmaxyx()
        lshift = (width-maxwidth)//2
        if lshift < 0:
          lshift = 0
    if hpos - topline < 0:
      topline = hpos
    elif choicestart + hpos - topline >= height:
      topline = choicestart + hpos - height + 1

'''
getdirmenu(scr, title)

  This method is used to print a file selection menu on scr
  The navigation begins from the current working directory
  The choices are the contents of the currently selected directory
  The selection will be a directory

  Returns ->
    on directoryext selection: path (str)
    on cancelled: None
'''
def getdirmenu(scr, title='', prompt='Select a directory'):
  # the path starts at the current working directory
  path = Path.cwd()
  body = [[prompt], [f'Dir: {path}']]
  topline = 0
  ch = 0
  # when we move to a new directory update the body text and reset pos
  while True:
    # get the sorted contents of the directory
    names = sorted([name for name in path.iterdir()])
    # only keep names we have read permission for
    names = [name for name in names if os.access(name, os.R_OK)]
    # finally, keep directories with the execute bit
    names = [str(name) for name in names if \
              name.is_dir() and os.access(name, os.X_OK)]
    # give an option to go up a level unless we are at the root
    if path.parents:
      names.insert(0, '..')
    # add the confirm option
    names = ['Select', ''] + names
    # get the response
    topline, ch = choicemenu(scr, title=title, body=body,
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None:
      return None
    # choice is Select
    if ch == 0:
      return f'{path}'
    # we selected to go up
    if names[ch] == '..':
      path = path.parent
      body[-1][-1] = f'Dir: {path}'
      ch = 0
      topline = 0
    # our selection is a subdirectory
    else:
      path = path / names[ch]
      body[-1][-1] = f'Dir: {path}'
      ch = 0
      topline = 0

'''
getfilemenu(scr, title)

  This method is used to print a file selection menu on scr
  The navigation begins from the current working directory
  The choices are the contents of the currently selected directory

  perm is the needed permissions for files,
    all files require read

  Returns ->
    on file selection: filename
    on cancelled: None
'''
def getfilemenu(scr, title='', prompt='Select a file', perm=os.R_OK):
  # the path starts at the current working directory
  path = Path.cwd()
  body = [[prompt], [f'Path: {path}']]
  topline = 0
  ch = 0
  # when we move to a new directory update the body text and reset pos
  while True:
    # get the sorted contents of the directory
    names = sorted([name for name in path.iterdir()])
    # only keep names we have (at least) read permission for
    names = [name for name in names if os.access(name, os.R_OK)]
    # finally, keep files and any directories that also have the execute bit
    names = [name for name in names if \
              (name.is_file() and os.access(name, perm)) or \
              (name.is_dir() and os.access(name, os.X_OK))]
    # squash to strings and reorder
    # directories before files, directories end with os.path.sep
    names = [str(name.name)+os.path.sep for name in names if name.is_dir()] + \
            [''] + \
            [str(name.name) for name in names if name.is_file()]
    # give an option to go up a level unless we are at the root
    if path.parents:
      names.insert(0, '..')
    # get the response
    topline, ch = choicemenu(scr, title=title, body=body,
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None: return None
    # we selected to go up
    if names[ch] == '..':
      path = path.parent
      body[-1][-1] = f'Path: {path}'
      ch = 0
      topline = 0
    # our selection is a subdirectory
    elif names[ch].endswith(os.path.sep):
      path = path / names[ch]
      body[-1][-1] = f'Path: {path}'
      ch = 0
      topline = 0
    # our selection was a file
    else:
      return f'{path / names[ch]}'

'''
drawsplitpane(scr,
              lhs, lpos, rhs, rpos,
              highlight, paneshmt,
              ltitle, rtitle, linenums)

  This method draws a split pane view
  lhs and rhs are lists of strings with titles ltitle and rtitle
  lpos and rpos determines which row/col is the top left of each pane
  {l,r}pos[0] = first row, [1] = first col
  last row = {l,r}pos[0] + height - 1
  The screen is divided vertically into 2 segments
  The division is shifted by paneshmt
    where 0 is vertical bar at width/2 -- neg/pos shifts left/right
  With linenums=True, a line number can be printed to the left of a line
    (if {l,r}pos[1] is negative)
  The screen is cleared, strings added to screen, then refreshed

                          width
            middle
+-------------|-------------+
'''
def drawsplitpane(scr,
                  lhs, lpos, rhs, rpos,
                  highlight, paneshmt=0,
                  ltitle='left', rtitle='right',
                  linenums=True):
  infocolor = curses.color_pair(2) | curses.A_BOLD
  # clear the screen
  scr.erase()
  # the current height and width (will change if window is resized)
  height, width = scr.getmaxyx()
  # paneshmt can be negative or positive for left/right
  middle = width//2 + paneshmt
  # get max lengths of line numbers (if linenums=True)
  # the bottom printed line will have the longest number
  lilen = lpos[0]+height
  if lilen > len(lhs):
    lilen = len(lhs)
  lilen = len(str(lilen)) if lilen > 0 else 0
  rilen = rpos[0]+height
  if rilen > len(rhs):
    rilen = len(rhs)
  rilen = len(str(rilen)) if rilen > 0 else 0
  drawvline = None
  # rhs is shifted out of view
  # +------------|+
  if middle > width - 3:
    # we only print the left side
    printside = lambda side: side==lhs
    # zero chars given for rhs
    rhslen = 0
    # width chars given for lhs
    lhslen = width-1
  # lhs is shifted out of view
  # +|------------+
  elif middle < 1:
    printside = lambda side: side==rhs
    rstart = 0
    rhslen = width-1
    lhslen = 0
  # have both left and right panes
  else:
    # set drawvline to not None here
    drawvline = False
    printside = lambda side: True
    # middle is vbar, rstart=vbar+1, lhslen=vbar-1
    rstart = middle + 1
    rhslen = width - rstart - 1
    lhslen = middle
  ltitle = ltitle[:lhslen]
  rtitle = rtitle[:rhslen]
  haveline = lambda index, lines: \
      printside(lines) and index >= 0 and index < len(lines)
  # set highlighted lines to an immutable tuple of indices
  if highlight:
    if drawvline is None:
      highlight = ()
    else:
      highlight = tuple([i for i in range(height) if \
                haveline(i+lpos[0], lhs) and haveline(i+rpos[0], rhs) and \
                lhs[i+lpos[0]].strip() == rhs[i+rpos[0]].strip()])
  else:
    highlight = ()
  # add lines
  for i in range(height):
    # lhs and rhs both have a line to print here
    if drawvline is not None:
      drawvline = True
    # set color, standard or highlight
    if i in highlight:
      color = curses.color_pair(1) | curses.A_BOLD
    else:
      color = curses.color_pair(0)
    # draw lhs
    if lhslen > 0:
      if i+lpos[0] == -2:
        scr.hline(i, 0, curses.ACS_HLINE, lhslen,
                  curses.color_pair(1) | curses.A_STANDOUT)
      elif i+lpos[0] == -1:
        scr.addnstr(i, 1, ltitle, len(ltitle), infocolor)
        padlen = len(ltitle)
        if padlen+2 < lhslen:
          pad = ' '*(lhslen-padlen-2)
          scr.addnstr(i, padlen+2, pad, len(pad),
                  curses.color_pair(4) | curses.A_DIM)
      elif i+lpos[0] == len(lhs):
        scr.hline(i, 0, curses.ACS_HLINE, lhslen,
                  curses.color_pair(1) | curses.A_STANDOUT)
      elif haveline(i+lpos[0], lhs):
        if lpos[1] < 0:
          lindex = f'{lpos[0]+i+1:{lilen}d}'[lpos[1]:]
          if linenums:
            scr.addnstr(i, 0, lindex, lhslen, infocolor)
          lindex = len(lindex)
          if lhslen-lindex > 0:
            scr.addnstr(i, lindex, lhs[lpos[0]+i][:lhslen-lindex],
                        lhslen-lindex, color)
        else:
          scr.addnstr(i, 0,
                      lhs[lpos[0]+i][lpos[1]:lpos[1]+lhslen],
                      lhslen, color)
      elif drawvline is not None:
        drawvline = False
      if drawvline:
        scr.addch(i, middle, curses.ACS_VLINE,
              curses.color_pair(1) | curses.A_STANDOUT)
    # draw rhs
    if rhslen > 0:
      if drawvline is not None and not drawvline:
        drawvline = True
      if i+rpos[0] == -2:
        scr.hline(i, rstart, curses.ACS_HLINE, rhslen,
                  curses.color_pair(1) | curses.A_STANDOUT)
      elif i+rpos[0] == -1:
        padlen = len(rtitle)
        if padlen+1 < rhslen:
          pad = ' '*(rhslen-padlen-1)
          scr.addnstr(i, rstart, pad, len(pad),
                  curses.color_pair(4) | curses.A_DIM)
        scr.addnstr(i, width-len(rtitle)-1,
                    rtitle, len(rtitle), infocolor)
      elif i+rpos[0] == len(rhs):
        scr.hline(i, rstart, curses.ACS_HLINE, rhslen,
                  curses.color_pair(1) | curses.A_STANDOUT)
      elif haveline(i+rpos[0], rhs):
        if rpos[1] < 0:
          rindex = f'{rpos[0]+i+1:{rilen}d}'[rpos[1]:]
          if linenums:
            scr.addnstr(i, rstart, rindex, rhslen, infocolor)
          rindex = len(rindex)
          if rindex < rhslen:
            scr.addnstr(i, rstart+rindex, rhs[rpos[0]+i][:rhslen-rindex],
                        rhslen-rindex, color)
        else:
          scr.addnstr(i, rstart, rhs[rpos[0]+i][rpos[1]:rpos[1]+rhslen],
                      rhslen, color)
      elif drawvline is not None:
        drawvline = False
      if drawvline:
        scr.addch(i, middle, curses.ACS_VLINE,
              curses.color_pair(1) | curses.A_STANDOUT)
  scr.refresh()
