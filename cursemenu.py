#! /usr/bin/env python3

import curses, os

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
filemenu(scr, title)

  This method is used to print a file selection menu on scr
  The navigation begins from the current working directory
  The choices are the contents of the currently selected directory
  A file opened must be a text file

  Returns -> the file.readlines() list (or None if cancelled)
'''
def filemenu(scr, title=''):
  # the path starts at the current working directory
  path = os.getcwd()
  error = None
  body = [['Select a text file'], ['Path: ' + path]]
  topline = 0
  ch = 0
  while True:
    # give an option to go up a level unless we are at the root
    if path == '': path = '/'
    names = ['../'] if path != '/' else []
    # add the contents of the directory
    names += [name+'/' for name in os.listdir(path) \
                        if os.path.isdir(path+'/'+name)]
    names += [name for name in os.listdir(path) \
                        if os.path.isfile(path+'/'+name)]
    names.sort()
    # get the response
    topline, ch = showmenu(scr, title=title, body=body, err=error,
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None: return None, None
    # reset the error message
    error = None
    # if we selected to go up or our selection is a subdirectory
    if names[ch][-1] == '/':
      # if we chose to go up remove the last directory from the path
      if names[ch] == '../':
        path = '/'.join(path.split('/')[:-1])
        # the root will become an empty string
        if path == '': path = '/'
      # we chose a directory from our path
      else:
        # test to see if we can get a list of the directory contents
        names[ch] = names[ch][:-1]
        testpath = path + names[ch] if path == '/' else path + '/' + names[ch]
        try: os.listdir(testpath)
        except Exception as e:
          # if we can't read the directory set an error string and continue
          error = str(e).split(':')
          continue
        # if we could read the directory set the path
        path = testpath
      # update the path in the body text
      body[-1][-1] = 'Path: ' + path
      ch = 0
      topline = 0
    # our selection was a file
    else:
      # try to read the file
      try:
        if path == '/': path = ''
        # reading the file will fail without permissions
        # or if the file is definitely not a text file
        # (some binary files will pass here and throw an exception if used)
        with open(path+'/'+names[ch]) as infile:
          contents = infile.readlines()
          if not contents:
            error = 'File \"' + names[ch] + '\" appears empty'
          for line in contents:
            if any(not isinstance(c, str) for c in line):
              error = 'File \"' + names[ch] + '\" not printable'
              break
          if not error: return contents, names[ch]
      except Exception as e:
        error = str(e).split(':')

'''
drawsplitpane(scr, lhs, lpos, rhs, rpos, highlight, paneshmt, halfgap)

  This method draws a split pane view
  lhs and rhs are lists of strings
  lpos and rpos determines which row/col is the top left of each pane
  The screen is divided vertically into 2 segments with a gap of halfgap*2
  The screen is cleared, strings added to screen, then refreshed
  Returns the current height, width
'''
def drawsplitpane(scr, lhs, lpos, rhs, rpos, highlight, paneshmt=0, halfgap=2):
  infocolor = curses.color_pair(2) | curses.A_BOLD
  # clear the screen
  scr.erase()
  # the current height and width (will change if window is resized)
  height, width = scr.getmaxyx()
  # paneshmt can be negative or positive for left/right
  middle = width//2 + paneshmt
  # if the middle is shifted left or right
  if paneshmt != 0:
    # if the rhs was shifted out of view
    if middle >= width - halfgap:
      scr.insstr(0, 1, 'left', infocolor)
      rstart = width
      lstop = width + lpos[1]
    # if the lhs was shifted out of view
    elif middle <= halfgap:
      scr.insstr(0, width-6, 'right', infocolor)
      rstart = 0
      lstop = lpos[1]
    # otherwise the boundary is still in the middle
    else:
      scr.insstr(0, 1, 'left', infocolor)
      scr.insstr(0, width-6, 'right', infocolor)
      rstart = middle + halfgap
      lstop = middle - halfgap + lpos[1]
  else:
    rstart = middle + halfgap
    lstop = middle - halfgap + lpos[1]
    scr.insstr(0, 1, 'left', infocolor)
    scr.insstr(0, width-11, 'right', infocolor)
  rstop = width - rstart + rpos[1]
  # the default color is standard color
  color = curses.color_pair(0)
  # add lines
  for i in range(1, height):
    if highlight:
      # if the strings match (without leading/trailing space)
      if i+lpos[0] >= 0 and i+rpos[0] >=0 and \
            i+lpos[0] < len(lhs) and i+rpos[0] < len(rhs) and \
            lhs[lpos[0]+i].strip() == rhs[rpos[0]+i].strip():
        # make bold green
        color = curses.color_pair(1) | curses.A_BOLD
      # otherwise standard color
      else: color = curses.color_pair(0)
    # draw lhs if we have a row here
    if lstop != lpos[1]:
      if i+lpos[0] >= 0 and i+lpos[0] < len(lhs):
        scr.insstr(i, 0, lhs[lpos[0]+i][lpos[1]:lstop], color)
      elif i+lpos[0] == len(lhs):
        scr.insstr(i, 1, 'END', infocolor)
    # draw rhs if we have a row here
    if rstop != rpos[1]:
      if i+rpos[0] >= 0 and i+rpos[0] < len(rhs):
        scr.insstr(i, rstart, rhs[rpos[0]+i][rpos[1]:rstop], color)
      elif i+rpos[0] == len(rhs):
        scr.insstr(i, width-4, 'END', infocolor)
  scr.refresh()
  return height, width

# vim: tabstop=2 shiftwidth=2 expandtab
