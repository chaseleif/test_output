#! /usr/bin/env python3

import curses, os, unicodedata
from pathlib import Path
from string import printable

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
showmenu(scr, title, body, err, choices, infobox, curs, hpos)

  This method is used to print a text menu using the screen scr

  The title is drawn on the first line
  An empty line separates the title from the body
  The body is a list of lists of strings
  Each is separated by a line
  The error, if present, is then printed in error color
  The remaining lines are "choice" lines which can be scrolled
  The current selection at hpos will be highlighted

  The user makes their selection with navigation keys
  When enter is pressed, the corresponding index of choices is returned
  If escape, q, or Q is pressed, None is returned

  If infobox is True this method will return on the first keypress

  curses.curs_set is set with the curs parameter
    0 is hidden
    1 is (possibly) an underscore/line
    2 is (possibly) a block
'''
def showmenu(scr,
              title='', body=[[]], err=None, choices=[],
              infobox=False, curs=0, topline=0, hpos=0):
  if hpos < topline: hpos = topline
  # track width
  maxwidth = len(title)
  for section in body:
    for line in section: maxwidth = max(len(line),maxwidth)
  errorlen = 1
  if type(err) is str: maxwidth = max(len(err),maxwidth)
  elif type(err) is list:
    errorlen = len(err)
    for e in err: maxwidth = max(len(e),maxwidth)
  for line in choices: maxwidth = max(len(line),maxwidth)
  # set colors to be used
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  activecolor = curses.color_pair(1) | curses.A_BOLD
  errorcolor = curses.color_pair(3) | curses.A_BOLD
  # when the counter hits zero make the error disappear
  errorcounter = None
  while True:
    if err and errorcounter == 0:
      topline -= errorlen + 1
      if topline < 0: topline = 0
      err = None
    # get the current dimensions
    height, width = scr.getmaxyx()
    # get side buffer
    lshift = 0
    if maxwidth < width: lshift = (width-maxwidth)//2
    # clear the screen
    scr.erase()
    # add the title
    scr.insstr(0, 0+lshift, title, titlecolor)
    # track the line number we are printing to
    linenum = 1
    for section in body:
      # print all lines in a section of the body
      for line in section:
        linenum += 1
        scr.insstr(linenum, 4+lshift, line, itemcolor)
      # separate body sections by a newline
      linenum += 1
    # separate body from remainder with another newline
    linenum += 1
    if err:
      # print an error message if we have one, add 2 lines
      if type(err) is list:
        for e in err:
          if e == '': continue
          scr.insstr(linenum, 4+lshift, e, errorcolor)
          linenum += 1
        linenum -= 1
      else:
        scr.insstr(linenum, 4+lshift, err, errorcolor)
      linenum += 2
      if errorcounter is None:
        errorcounter = 5
        if height-linenum < len(choices):
          topline += errorlen + 1
          # if the error pushes hpos out of sight
          if topline > hpos: topline = hpos
      else:
        errorcounter -= 1
    # track the actual top line of the choices
    actualtop = linenum
    # i is zero indexed matching hpos
    for i, line in enumerate(choices):
      # we cannot go beyond height if choices is a long list
      if linenum == height: break
      # print this line
      if i >= topline:
        # set the color to active if this is our highlight position
        color = activecolor if i == hpos else itemcolor
        scr.insstr(linenum, 4+lshift, line, color)
        linenum += 1
    # set the cursor according to the argument and refresh the screen
    if curs != 0:
      cursorcol = 4 + lshift + len(choices[hpos])
      if cursorcol < width:
        scr.move(actualtop + hpos - topline, cursorcol)
        curses.curs_set(curs)
    scr.refresh()
    # get our response, reset the cursor and process the response
    ch = scr.getch()
    curses.curs_set(0)
    # allow to return without making a selection:
    # escape = 27, 'Q'=81, 'q'=113
    if ch in [27, 81, 113]: return None, None
    # this argument indicates we return immediately on a keypress
    if infobox: return
    # go to the top
    elif ch == curses.KEY_HOME:
      hpos = 0
      topline = 0
    # go to the bottom
    elif ch == curses.KEY_END:
      if actualtop + len(choices) > height:
        topline = len(choices) - height + actualtop
        hpos = len(choices) - 1
    # go up
    elif ch == curses.KEY_UP:
      if hpos > 0:
        hpos -= 1
        if actualtop + hpos - topline < actualtop: topline -= 1
    # go down
    elif ch == curses.KEY_DOWN:
      if hpos < len(choices) - 1:
        hpos += 1
        if actualtop + hpos - topline == height: topline += 1
    # jump up
    elif ch == curses.KEY_PPAGE and hpos > 0:
      hpos -= 4
      if hpos - topline < 0: topline = hpos
      if hpos < 0:
        hpos = 0
        topline = 0
    # jump down
    elif ch == curses.KEY_NPAGE:
      hpos += 4
      if hpos >= len(choices) - 1: hpos = len(choices) - 1
      if actualtop + hpos - topline >= height:
        topline += actualtop + hpos - topline - height + 1
    # on enter we return our highlighted position
    elif ch in [curses.KEY_ENTER, 10, 13]: return topline, hpos

'''
gettextfilemenu(scr, title)

  This method is used to print a file selection menu on scr
  The navigation begins from the current working directory
  The choices are the contents of the currently selected directory
  A file opened must be a text file

  Returns ->
    on text file selection: [lines], filename
    on cancelled: None, None
'''
def gettextfilemenu(scr, title=''):
  # the path starts at the current working directory
  path = Path.cwd()
  error = None
  body = [['Select a text file'], [f'Path: {path}']]
  topline = 0
  ch = 0
  # when we move to a new directory update the body text and reset pos
  while True:
    # get the sorted contents of the directory
    names = sorted([name for name in path.iterdir()])
    # only keep names we have read permission for
    names = [name for name in names if os.access(name, os.R_OK)]
    # finally, keep files and any directories with the execute bit
    names = [name for name in names if name.is_file() or \
              (name.is_dir() and os.access(name, os.X_OK))]
    # squash to strings and reorder
    # directories before files, directories end with os.path.sep
    names = [str(name.name)+os.path.sep for name in names if name.is_dir()] + \
            [str(name.name) for name in names if name.is_file()]
    # give an option to go up a level unless we are at the root
    if path.parents:
      names.insert(0, '..')
    # get the response
    topline, ch = showmenu(scr, title=title, body=body, err=error,
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None: return None, None
    # reset the error message
    error = None
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
      # return the file contents+name if we can read it as strings
      try:
        with open(path / names[ch], 'r') as infile:
          contents = infile.readlines()
        if not contents:
          error = 'File \"' + names[ch] + '\" appears empty'
        else:
          return contents, names[ch]
      except Exception as e:
        error = str(e).split(':')

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
