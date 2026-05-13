#! /usr/bin/env python3

import curses, os, re, signal, sys
from collections import deque
from curses import ascii
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

  if body, it is a list of strings
  if lines are within body, they are printed followed by a newline

  prompt is printed following the body, if it is not empty

  curses.curs_set is set with curs
    0 is hidden
    1 is (possibly) an underscore/line
    2 is (possibly) a block

  confirm is a list of accepting keypresses
  if confirm is empty then any return from getch is accepting

  the accepting result of getch is returned from this function
'''
def modalwindow(scr, title='', body=[], err=[], curs=0,
                prompt='Press the any key to continue . . . ', confirm=[]):
  if body:
    maxwidth = max(len(l) for l in body)
  else:
    maxwidth=0
  if prompt:
    maxwidth = max(maxwidth,len(prompt))
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
      if type(err) is list:
        for e in err:
            linenum += 1
            if linenum >= height: break
            if e:
              scr.insstr(linenum, lshift, e, errorcolor)
              cursorcol = len(e)
      else:
        linenum += 1
        if linenum < height:
          scr.insstr(linenum, lshift, err, errorcolor)
          cursorcol = len(err)
    if body:
      linenum += 1
      for line in body:
        linenum += 1
        if line:
          if linenum >= height: break
          scr.insstr(linenum, lshift, line, itemcolor)
          cursorcol = len(line)
    if prompt:
      linenum += 2
      if linenum >= height: break
      scr.insstr(linenum, lshift, prompt, itemcolor)
      cursorcol = len(prompt)
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

def statusbarwindow(scr, status, title='Status', body=[], err=[]):
  try:
    maxwidth = max(len(l) for l in body)
  except ValueError:
    maxwidth=0
  if isinstance(err, str):
    maxwidth = max(maxwidth, len(err))
  elif err:
    maxwidth = max(maxwidth, max(len(e) for e in err))
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  errorcolor = curses.color_pair(3) | curses.A_BOLD
  height, width = scr.getmaxyx()
  lshift = (width-maxwidth)//2
  if lshift < 0:
    lshift = 0
  scr.erase()
  linenum = 0
  if title:
    scr.insstr(linenum, (width-len(title))//2, title, titlecolor)
  if err:
    linenum += 1
    if type(err) is list:
      for e in err:
        linenum += 1
        if linenum >= height: break
        if e:
          scr.insstr(linenum, lshift, e, errorcolor)
    else:
      linenum += 1
      if linenum < height:
        scr.insstr(linenum, lshift, err, errorcolor)
  if body:
    linenum += 1
    # we have height-linenum-1 lines remaining we can print on
    nlines = height - linenum - 1
    if nlines > 0:
      lines = body[-nlines:]
      for line in lines:
        linenum += 1
        if line:
          scr.insstr(linenum, lshift, line, itemcolor)
  scr.insstr(0, height-1, status, itemcolor)



'''
getinputmenu(scr, title, prompt)
'''
def getinputmenu(scr, title='', prompt='Enter input:', val='',
                  allowemptystr=False):
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  # val and history of val for undo
  history = deque(maxlen=32)
  height, width = scr.getmaxyx()
  # allow ctrl-z to undo (not suspend process)
  undo = False
  def ctrlz(signum, frame):
    nonlocal undo
    undo = True
  # just in case someone else handles SIGTSTP
  prevSIGTSTP = signal.getsignal(signal.SIGTSTP)
  signal.signal(signal.SIGTSTP, ctrlz)
  # cursor offset from end of string (number of columns to move left)
  cursleft = 0
  try:
    curses.curs_set(2)
    while True:
      scr.erase()
      lpos = (width-len(title))//2
      if lpos < 0:
        lpos = 0
      scr.insstr(0, lpos, title, titlecolor)
      lpos = (width-len(prompt))//2
      if lpos < 0:
        lpos = 0
      if 2 >= height:
        break
      scr.insstr(2, lpos, prompt, itemcolor)
      if val:
        line = 4
        lpos = (width-len(val))//2
        if lpos < 0:
          lpos = 0
        # when len(val) becomes large lpos goes to zero
        # we can only put width chars in line 4
        scr.insstr(4, lpos, val[:width], itemcolor)
        # the cursor moves right by len(val)
        lpos += len(val)
        # we are on line 4
        line = 4
        # if we need to break prints we track consumed chars
        consumed = 0
        # the lpos didn't fit within the width
        while lpos > width:
          # we consumed width chars
          consumed += width
          # advance the line and break if we go out-of-screen
          line += 1
          if line >= height:
            break
          # insert the next line and decrement lpos
          scr.insstr(line, 0, val[consumed:consumed+width], itemcolor)
          lpos -= width
        # cursor should now be at (line, lpos-cursleft)
        # we need to shift the cursor left by cursleft
        shmt = cursleft
        # we can do this in line 4
        if lpos - shmt >= 0:
          lpos -= shmt
        # we are going to have to go up to a previous line
        else:
          # move the cursor up somewhere
          while lpos - shmt < 0:
            # previous line
            line -= 1
            # reduce shmt by chars in the line
            shmt -= lpos
            # set lpos to the width of the new line
            lpos = width
          # lpos >= shmt, we can now take shmt out of lpos
          lpos -= shmt
        # we have to be able to move the cursor somewhere in the screen
        if lpos == width:
          line += 1
          lpos = 0
        if line >= height:
          break
        # move the cursor
        scr.move(line, lpos)
      else:
        # no text yet, just move the cursor if we have height > 4
        if 4 >= height:
          break
        scr.move(4, width//2)
      scr.refresh()
      ret = False
      while True:
        try:
          # we need wch to get ctrl-z (at least sometimes)
          ch = scr.get_wch()
        # we'll get a 'no input' error if SIGTSTP is caught
        except curses.error as e:
          # ctrl-z
          if undo:
            undo = False
            if len(history) > 0:
              val = history.pop()
              break
            continue
          # ignore 'no input' errors
          if str(e) == 'no input':
            continue
          raise
        # handle regular int vals
        if isinstance(ch, int):
          # escape
          if ch == 27:
            return None
          # enter
          if ch in [curses.KEY_ENTER, 10, 13]:
            if allowemptystr:
              return val
            return val if val else None
          # delete or 0x7f
          if ch in [curses.KEY_DC, 127]:
            if cursleft > 0:
              # we act the same as backspace, except with cursleft 1 less
              cursleft -= 1
              history.append(val)
              # if cursor is at the end we just remove
              if cursleft == 0:
                val = val[:-1]
              # otherwise we slice out our position
              else:
                val = val[:-cursleft][:-1] + val[-cursleft:]
                # if we remove the first char we have to decrement cursleft
                if cursleft == len(val):
                  cursleft -= 1
              cursleft += 1
              cursleft = min(cursleft, len(val))
              break
          # backspace or \b
          if ch in [curses.KEY_BACKSPACE, 8]:
            if val and cursleft < len(val):
              history.append(val)
              # if cursor is at the end we just remove
              if cursleft == 0:
                val = val[:-1]
              # otherwise we slice out our position
              else:
                val = val[:-cursleft][:-1] + val[-cursleft:]
                # if we remove the first char we have to decrement cursleft
                cursleft = min(cursleft, len(val))
              break
          if ch == curses.KEY_RESIZE:
            height, width = scr.getmaxyx()
            break
          # ctrl-z
          if ch == ascii.SUB and lastval != val:
            val = history.pop()
            break
          # move the insert cursor left/right
          if ch == curses.KEY_LEFT and cursleft < len(val):
            cursleft += 1
            break
          if ch == curses.KEY_RIGHT and cursleft > 0:
            cursleft -= 1
            break
          if ch == curses.KEY_HOME and cursleft != len(val):
            cursleft = len(val)
            break
          if ch == curses.KEY_END and cursleft > 0:
            cursleft = 0
            break
          # not handling this int(ch)
          continue
        # isinstance(ch, str) == True
        # since we use wch we can have strings, handle those
        # escape
        if ch == '\x1b':
          return None
        # enter
        if ch in ['\r', '\n']:
          if allowemptystr:
            return val
          return val if val else None
        # backspace
        if ch in ['\b', '\x7f']:
          if val:
            history.append(val)
            if cursleft == 0:
              val = val[:-1]
            # otherwise we slice out our position
            else:
              val = val[:-cursleft][:-1] + val[-cursleft:]
              # if we remove the first char we have to decrement cursleft
              if cursleft > len(val):
                cursleft -= 1
          break
        # some other string, this is input
        history.append(val)
        # cursleft is 0 we append chars
        if cursleft == 0:
          val += ch
        # otherwise we need to put the char in the middle
        else:
          val = val[:-cursleft] + ch + val[-cursleft:]
        # NOTE:
        # 10ms between inputs to combine rapid chars or paste
        # set getinputmenu.timeout = an int (milliseconds)
        #  you may possibly need to adjust the timeout:
        #   if you gobble multiple chars without printing them (decrease)
        #   if you paste and the paste is broken (increase)
        # this shouldn't be much of a problem, really just a fancy feature
        scr.timeout(getinputmenu.timeout)
        try:
          while True:
            try:
              ch = scr.get_wch()
            except curses.error:
              break
            if not isinstance(ch, str):
              # NOTE: not re-handling non chars, this is probably fine
              break
            # same char splicing as above
            if cursleft == 0:
              val += ch
            else:
              val = val[:-cursleft] + ch + val[-cursleft:]
        # set getch to be blocking again
        finally:
          scr.timeout(-1)
        # we took at least 1 char, break to print it
        break
  finally:
    # hide the cursor
    curses.curs_set(0)
    # restore the SIGTSTP signal handler, if there was one
    signal.signal(signal.SIGTSTP, prevSIGTSTP)
getinputmenu.timeout=10

'''
choicemenu(scr, title, body, choices, infobox, curs, hpos)

  This method is used to print a text menu using the screen scr

  The title is drawn on the first line
  An empty line separates the title from the body
  The body is a list of strings

  The remaining lines are "choice" lines which can be scrolled
  The current selection at hpos will be highlighted
  Empty strings can be used
    but their indices should be included in disabled
    unless you an empty string is a valid return
  Disabled is a list of indices that are disabled and shouldn't be chosen

  The user makes their selection with navigation keys
  When enter is pressed, the corresponding index of choices is returned
  If escape, q, or Q is pressed, None is returned

  curses.curs_set is set with the curs parameter
    0 is hidden
    1 is (possibly) an underscore/line
    2 is (possibly) a block
'''
def choicemenu(scr, title='', multi=False, helpkeys=[], helpstr=True,
              body=[], choices=[], disabled=[], chosen=[], epilogue=[],
              curs=0, topline=0, hpos=0):
  if hpos < topline: hpos = topline
  havechoice = 0
  while havechoice in disabled:
    havechoice += 1
  havechoice += len([choice for choice in choices if not choice])
  havechoice = havechoice < len(choices)
  # track width to center text
  maxwidth = 0
  if body:
    maxwidth =  max(maxwidth,max(len(l) for l in body))
  if choices:
    maxwidth = max(maxwidth, max(len(c) for c in choices))
  if multi:
    maxwidth += 2
  # set colors to be used
  disabledcolor = curses.color_pair(5) | curses.A_BOLD
  titlecolor = curses.color_pair(2) | curses.A_BOLD
  itemcolor = curses.color_pair(1)
  activecolor = curses.color_pair(1) | curses.A_BOLD
  # get the dimensions
  height, width = scr.getmaxyx()
  # get side buffer
  lshift = (width-maxwidth)//2
  if lshift < 0:
    lshift = 0
  if multi:
    lshift += 2
  # amount shifted right for long lines
  rshift = [0 for _ in range(len(choices))]
  # toplines include the title and body, these are before the choices
  choicestart = 2 + len(body)
  maxhpos = len(choices) - 1
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
    # print all lines of the body
    for line in body:
      linenum += 1
      if linenum >= height: break
      if line:
        scr.insstr(linenum, lshift, line, itemcolor)
    # separate body from remainder with another newline
    linenum += 1
    for i, line in enumerate(choices[topline:]):
      # we cannot go beyond height if choices is a long list
      if linenum >= height: break
      if not line:
        linenum += 1
        continue
      # set the color to active if this is our highlight position
      if i+topline == hpos and lshift > 1:
        scr.insch(linenum, lshift-2, curses.ACS_DIAMOND, activecolor)
      color = disabledcolor if havechoice and i+topline in disabled else \
              activecolor if i+topline == hpos else \
              activecolor if line in chosen else itemcolor
      scr.insstr(linenum, lshift, line[rshift[i+topline]:], color)
      linenum += 1
    if helpkeys and helpstr:
      linenum += 1
      if linenum < height:
        line = 'Help: {' + \
                ', '.join([chr(k) if isinstance(k,int) else f'{k}' \
                            for k in helpkeys]) + \
                '}'
        scr.insstr(linenum, lshift, line, itemcolor)
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
                    curses.KEY_RIGHT, curses.KEY_LEFT, curses.KEY_RESIZE):
      # get our response, reset the cursor and process the response
      ch = scr.getch()
      curses.curs_set(0)
      # if the key is in helpkeys, return it
      if ch in helpkeys:
        return topline, ch
      # on enter we return our highlighted position
      if ch in [curses.KEY_ENTER, 10, 13]:
        if not havechoice:
          return None, None
        if hpos in disabled:
          continue
        # multi-select we return this list on the first choice
        # the first choice should be a variation of 'confirm'
        if multi:
          if hpos == 0:
            return None, chosen
          if choices[hpos] in chosen:
            del chosen[chosen.index(choices[hpos])]
          else:
            chosen.append(choices[hpos])
          break
        return topline, hpos
      # allow to return without making a selection with escape or q
      if ch in [27, 81, 113]: return None, None
      # the direction we are moving (up=-1, neither=0, down=1)
      direction = 0
      # go to the top
      if ch == curses.KEY_HOME:
        rshift = [0 for _ in rshift]
        hpos = 0
        topline = 0
        direction = -1
      # go to the bottom
      elif ch == curses.KEY_END and hpos < maxhpos:
        hpos = maxhpos
        direction = 1
      # go up
      elif ch == curses.KEY_UP and hpos > 0:
        hpos -= 1
        direction = -1
      # go down
      elif ch == curses.KEY_DOWN and hpos < maxhpos:
        hpos += 1
        direction = 1
      # jump up
      elif ch == curses.KEY_PPAGE and hpos > 0:
        hpos -= 4
        if hpos < 0:
          hpos = 0
          topline = 0
        direction = -1
      # jump down
      elif ch == curses.KEY_NPAGE and hpos < maxhpos:
        hpos += 4
        if hpos > maxhpos:
          hpos = maxhpos
        direction = 1
      # move right
      elif ch == curses.KEY_RIGHT:
        if lshift+len(choices[hpos][rshift[hpos]:]) > width:
          rshift[hpos] += 1
      elif ch == curses.KEY_LEFT and rshift[hpos] > 0:
        rshift[hpos] -= 1
      elif ch == curses.KEY_RESIZE:
        rshift = [0 for _ in rshift]
        # get new dimensions
        height, width = scr.getmaxyx()
        lshift = (width-maxwidth)//2
        if lshift < 0:
          lshift = 0
        if multi:
          lshift += 2
    if direction != 0:
      while (havechoice and hpos in disabled) or \
            (hpos>=0 and hpos <= maxhpos and not choices[hpos]):
        hpos += direction
      # if we go OOB move us to the nearest choice
      if hpos == -1 or hpos > maxhpos:
        direction = -direction
        hpos += direction
        while (havechoice and hpos in disabled) or \
              (hpos>=0 and hpos <= maxhpos and not choices[hpos]):
          hpos += direction
        #we must be at a choice
    if hpos - topline < 0:
      topline = hpos
    elif choicestart + hpos - topline >= height:
      topline = choicestart + hpos - height + 1

def infowindow(scr, title='', body=[], curs=0):
  disabled = [i for i in range(len(body))]
  choicemenu(scr, title=title, curs=curs, choices=body, disabled=disabled)

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
def getdirmenu(scr, title='', prompt='Select a directory', allownew=True):
  # the path starts at the current working directory
  path = Path.cwd()
  body = [prompt, '', f'Dir: {path}', '']
  topline = 0
  ch = 0
  # when we move to a new directory update the body text and reset pos
  while True:
    # get the sorted contents of the directory
    try:
      names = sorted([name for name in path.iterdir()])
    # if we tried to create a directory we don't have permission to make
    except FileNotFoundError:
      return
    # only keep names we have read permission for
    names = [name for name in names if os.access(name, os.R_OK)]
    # finally, keep directories with the execute bit
    names = [str(name) for name in names if \
              name.is_dir() and os.access(name, os.X_OK)]
    # give an option to go up a level unless we are at the root
    if path.parents:
      names.insert(0, '..')
    # add the confirm option
    if allownew:
      names = ['Select directory',
              'Make subdirectory here', '\b\bChange directory:'] + \
              names
    else:
      names = ['Select directory',
              '\b\bChange directory:'] + names
    # get the response
    topline, ch = choicemenu(scr, title=title, body=body,
                            disabled=[names.index('\b\bChange directory:')],
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None:
      return None
    # choice is Select
    if ch == 0:
      return f'{path}'
    if allownew and ch == 1:
      dirname = getinputmenu(scr, title=title,
                            prompt="Enter new directory name:")
      if dirname is None:
        continue
      try:
        os.mkdir(path / dirname)
        return f'{path / dirname}'
      except FileExistsError:
        modalwindow(scr, title=title, err=f'Directory {dirname} is a file')
      except PermissionError:
        modalwindow(scr, title=title, err=f'No permission to create {dirname}')
      except Exception as e:
        modalwindow(scr, title=title,
                    err=[m.strip() for m in re.split(r'[:\n]+', str(e))])
    # we selected to go up
    elif names[ch] == '..':
      path = path.parent
      body[-2] = f'Dir: {path}'
      ch = 0
      topline = 0
    # our selection is a subdirectory
    else:
      path = path / names[ch]
      body[-2] = f'Dir: {path}'
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
def getfilemenu(scr, title='', prompt='Select a file', perm=os.R_OK, filere=''):
  # the path starts at the current working directory
  try:
    match = re.compile(filere)
  except Exception as e:
    modalwindow(scr, title=title, curs=2,
                body=['Exception during re.compile'],
                err=[m.strip() for m in re.split(r'[:\n]}',str(e))])
    return None
  path = Path.cwd()
  body = [prompt, '', f'Path: {path}', '']
  topline = 0
  ch = 1
  # when we move to a new directory update the body text and reset pos
  while True:
    # get the sorted contents of the directory
    names = sorted([name for name in path.iterdir()])
    # only keep names we have (at least) read permission for
    names = [name for name in names if os.access(name, os.R_OK)]
    # keep files with perm and any directories that also have the execute bit
    names = [name for name in names if \
              (name.is_file() and os.access(name, perm)) or \
              (name.is_dir() and os.access(name, os.X_OK))]
    # remove files that don't match the filere
    names = [name for name in names if not name.is_file() or \
              match.match(str(name))]
    # squash to strings and reorder
    # directories before files, directories end with os.path.sep
    names = [str(name.name)+os.path.sep for name in names if name.is_dir()] + \
            [''] + \
            [str(name.name) for name in names if name.is_file()]
    # give an option to go up a level unless we are at the root
    if path.parents:
      names.insert(0, '..')
    names = ['\b\bChange path:'] + names
    disabled = [0, names.index('')]
    names[disabled[-1]] = '\b\bSelect file:'
    # get the response
    topline, ch = choicemenu(scr, title=title, body=body, disabled=disabled,
                            choices=names, topline=topline, hpos=ch)
    # allow to return without opening a file:
    if ch is None: return None
    # we selected to go up
    if names[ch] == '..':
      path = path.parent
      body[-2] = f'Path: {path}'
      ch = 0
      topline = 0
    # our selection is a subdirectory
    elif names[ch].endswith(os.path.sep):
      path = path / names[ch]
      body[-2] = f'Path: {path}'
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
