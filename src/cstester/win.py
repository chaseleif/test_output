import curses, inspect, os, re, signal, sys
from collections import deque
from enum import Flag, auto
from inspect import getdoc
from pathlib import Path
from types import TracebackType
from typing import List, Literal, Optional, Tuple, Type, Union

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

class WinOpt(Flag):
  '''
  Flags for drawing windows can be combined with ``|`` (OR)

  Flag values are listed in order of precedence
  '''
  #: Disable vertical scrolling
  #: -- only **prints** (optionally) title, errorlines, bodylines, footerline
  #: -- returns **immediately**, as with :py:attr:`.RETURNIMM`
  #: -- ``NOSCROLL`` ignores all options besides the ``TAIL`` options
  NOSCROLL = auto()
  #: When not scrollable, split real-estate between error and body
  #: (by default, body may be hidden if error lines fill the screen)
  TAILBOTH = auto()
  #: When not scrollable prefer the body (error lines may then be hidden)
  TAILBODY = auto()
  #: Return None **immediately** (*without input*)
  RETURNIMM = auto()
  #: Return the **any** key
  RETURNANY = auto()
  #: Return on a provided key or :py:attr:`.CursesScreen.returnkeys`
  RETURNKEY = auto()
  #: Return a list of choices from the body
  #: -- provide a confirmation prompt or use ``choices[0]`` to confirm
  RETURNMUL = auto()
  #: Include the delete key as a returnkey, returns ``str('KEY_DC')``
  RETURNDEL = auto()
  #: Use :py:attr:`.CursesScreen.helpkeys` as helpkeys
  USEHELP = auto()
  #: Body is 1 "textbox" block -- no highlight and collective scroll
  TEXTBOX = auto()
  #: Show the cursor at the end of the footerline (*if possible*)
  SHOWCURS = auto()

class CursesScreen:
  '''
  Curses helper class to initialize and manage a curses screen
  '''
  #: when tabs are replaced, replace with this number of spaces
  tabsize = 2
  #: set inputtimeout = an int (milliseconds);
  #: NOTE:
  #: input timeout temporarily set to 10ms between inputs
  #: to combine rapid chars or paste,
  #: you may possibly need to adjust the timeout
  inputtimeout = 10
  #: Default return keys are :py:data:`curses.KEY_ENTER`, '\\r', '\\n'
  returnkeys = ('KEY_ENTER', '\r', '\n')
  #: Default cancel keys are '\\x1b' (escape), 'Q', 'q'
  cancelkeys = ('\x1b', 'Q', 'q')
  #: Default help keys are '?', 'H', 'h'
  helpkeys = ('?', 'H', 'h')

  def __init__(self) -> None:
    #: The curses window, set in :py:meth:`.initscr`
    self.scr = None
    #: Reference counter for safe deletion with nested references
    self.refcount = 0
    # setting colors to zero will use their default value
    # if the terminal can't do colors, then use of colors has no effect
    #: Regular item color, green on black
    self.itemcolor = 0
    #: Item color with bold
    self.activecolor = 0
    #: Item color with standout
    self.standoutcolor = 0
    #: Title color, bold white on black
    self.titlecolor = 0
    #: Error color, bold red on black
    self.errorcolor = 0
    #: Disabled color, bold black on black
    self.disabledcolor = 0
    #: Border color (with whitespace), dim black on cyan
    self.bordercolor = 0

  def __enter__(self) -> 'CursesScreen':
    '''
    This class is meant to be used in a context

    In enter, we call ``initscr()`` and on exit we call ``cleanup()``

    If ``curses`` isn't properly cleaned up,
      the terminal can be left in an unusable state
    '''
    self.initscr()
    return self

  def __exit__(self,
              type: Optional[Type[BaseException]],
              value: Optional[BaseException],
              traceback: Optional[TracebackType]) -> Optional[bool]:
    self.cleanup()

  def __del__(self) -> None:
    self.cleanup()

  def initscr(self) -> None:
    '''
    Increments :py:attr:`.refcount`
    and returns if :py:attr:`.scr` is already initialized

    Otherwise, initializes :py:attr:`.scr` and prepares :py:mod:`curses`

    :py:class:`curses.window` may not return the correct ``maxyx`` after
    window resize events. This was reported in
    `this issue <https://github.com/python/cpython/issues/46927>`_
    (yes, **opened shortly after GitHub was founded**) and is *still* present.
    There was `a PR <https://github.com/python/cpython/pull/133585>`_
    made **17 years later** to solve the problem, but it hasn't been merged.
    A workaround is to set and delete the ``LINES`` and ``COLUMNS``
    environment variables, *which is done here*,
    otherwise resize events won't update values obtained from
    :py:meth:`curses.window.getmaxyx`

    **Setup includes:**
      - :py:func:`curses.start_color` -- if :py:func:`curses.has_colors`
      - :py:func:`curses.cbreak` -- immediately respond to keypresses
      - :py:func:`curses.curs_set` -- set curs to ``0`` to hide the cursor
      - :py:func:`curses.noecho` -- suppress echo of keypresses
      - :py:func:`curses.nonl` -- leave newline mode, we handle all keys
      - :py:func:`curses.raw` -- we really do handle all of the keys!
      - :py:func:`curses.set_escdelay` -- "remove" escape delay
      - :py:func:`curses.set_tabsize` -- set number of spaces per tab
      - :py:meth:`curses.window.leaveok` -- don't move the cursor on updates
      - :py:meth:`curses.window.keypad` -- enable additional curses keys
    '''
    self.refcount += 1
    if self.scr is not None:
      return
    for key in ('LINES','COLUMNS'):
      os.environ[key]=key
      del os.environ[key]
    # get the std screen
    scr = curses.initscr()
    # we want to use colors
    curses.start_color()

    # we can use colors, make pairs from the default colors
    # COLOR_{ BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE }
    if curses.can_change_color():
      # we can use pair numbers from 1 ... (0 is standard)
      # initialize colors described in __init__
      curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
      self.itemcolor = curses.color_pair(1)
      self.activecolor = curses.color_pair(1) | curses.A_BOLD
      self.standoutcolor = curses.color_pair(1) | curses.A_STANDOUT
      curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
      self.titlecolor = curses.color_pair(2) | curses.A_BOLD
      curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
      self.errorcolor = curses.color_pair(3) | curses.A_BOLD
      curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_BLACK)
      self.disabledcolor = curses.color_pair(4) | curses.A_BOLD
      curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
      self.bordercolor = curses.color_pair(5) | curses.A_DIM
    # safe, just use default color but give them attributes
    elif curses.has_colors():
      self.activecolor = curses.A_BOLD
      self.standoutcolor = curses.A_STANDOUT
      self.titlecolor = curses.A_BOLD
      self.errorcolor = curses.A_BOLD
      self.disabledcolor = curses.A_DIM
      self.bordercolor = curses.A_STANDOUT

    # immediately response to keypresses
    curses.cbreak()

    # hide the cursor, 0=invisible, 1=normal, 2=very visible
    curses.curs_set(0)

    # suppress echo of keypresses
    curses.noecho()

    # leave newline mode
    curses.nonl()

    # we handle all keys
    curses.raw()

    # remove escape delay, escape is only to quit/return
    curses.set_escdelay(10)

    # tabs are supposed to be 2 spaces
    curses.set_tabsize(CursesScreen.tabsize)

    # reduce cursor movement, we don't need automatic cursor movement
    scr.leaveok(True)

    # enable use of curses info for curses.KEY_LEFT, etc.
    scr.keypad(True)
    self.scr = scr

  def cleanup(self) -> None:
    '''
    The cleanup method restores the terminal based on ``refcount``

    This allows for safe nested usage:
      - each instance that uses **CursesScreen** can call :py:meth:`.initscr`
      - each instance that calls :py:meth:`.initscr` **must** call :py:meth:`.cleanup`
      - when ``refcount`` becomes zero we restore the terminal
    '''
    if self.scr is not None:
      self.refcount -= 1
      if self.refcount != 0:
        return
      # restore the terminal
      curses.nocbreak()
      self.scr.keypad(False)
      curses.echo()
      curses.nl()
      curses.noraw()
      curses.endwin()
    self.scr = None

  def clearkeys(self) -> None:
    '''
    call :py:func:`curses.flushinp` to clear input buffers
    '''
    curses.flushinp()

  def statuswindow(self,
                  title: str,
                  status: str,
                  body: Optional[List[str]]=[],
                  err: Optional[List[str]]=[]) -> None:
    '''
    Method aimed toward status/progress windows

    Prints the title, followed by the error, followed by the body

    If the length of the error/body go beyond the screen height,
    only the last height lines are printed.

    The final line printed is the status string

    This method takes no input and immediately returns
    '''
    titlecolor = self.titlecolor
    itemcolor = self.itemcolor
    errorcolor = self.errorcolor
    height, width = self.scr.getmaxyx()
    lshift = max(len(l) for l in body) if body else 0
    if err:
      lshift = max(lshift, max(len(e) for e in err))
    lshift = max(0, (width-lshift)//2)
    self.scr.erase()
    self.scr.addstr(0, max(0, (width-len(title))//2), title[:width], titlecolor)
    linenum = 2
    if err:
      lines = err[::-1][:height-linenum-2][::-1]
      for e in lines:
        if linenum >= height-1: break
        if e:
          self.scr.addstr(linenum, lshift, e[:width], errorcolor)
        linenum += 1
      linenum += 1
    if body:
      lines = body[::-1][:height-linenum-2][::-1]
      for line in lines:
        if linenum >= height-1: break
        if line:
          self.scr.addstr(linenum, lshift, line[:width], itemcolor)
        linenum += 1
    self.scr.addstr(height-1, max(0, (width-len(status))//2),
                    status[:width], itemcolor)
    self.scr.refresh()

  def getinput(self, title: str, prompt: str,
                val: Optional[str]='') -> Optional[str]:
    '''
    Prompt the user for input using a modal input menu

    Args:
      title (str): Title for the input window
      prompt (str): Prompt text to display
      val (str): Optional initial value shown in input field

    Returns:
      Optional[str]: Entered string or None if cancelled
    '''
    titlecolor = self.titlecolor
    itemcolor = self.itemcolor
    # history of val for undo (ctrl-z)
    history = deque(maxlen=32)
    height, width = self.scr.getmaxyx()
    # cursor offset from end of string (number of columns to move left)
    cursleft = 0
    try:
      # restore cursor visibility
      curses.curs_set(2)
      # and movement updates
      self.scr.leaveok(False)
      while True:
        if 2 >= height:
          break
        self.scr.erase()
        self.scr.addstr(0, max(0, (width-len(title))//2),
                        title[:width], titlecolor)
        lpos = max(0, (width-len(prompt))//2)
        self.scr.addstr(2, max(0, (width-len(prompt))//2),
                        prompt[:width], itemcolor)
        if val:
          line = 4
          lpos = max(0, (width-len(val))//2)
          # when len(val) becomes large lpos goes to zero
          # we can only put width chars in line 4
          self.scr.addstr(4, lpos, val[:width], itemcolor)
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
            self.scr.addstr(line, 0, val[consumed:consumed+width], itemcolor)
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
          self.scr.move(line, lpos)
        else:
          # no text yet, just move the cursor if we have height > 4
          if 4 >= height:
            break
          self.scr.move(4, width//2)
        self.scr.refresh()
        while True:
          c = self.scr.getkey()
          # cancel
          if c in CursesScreen.cancelkeys:
            return None
          # enter
          if c in CursesScreen.returnkeys:
            return val
          # backspace
          if c in ('KEY_BACKSPACE', '\b'):
            if val:
              history.append(val)
              # remove the trailing char
              if cursleft == 0:
                val = val[:-1]
              # otherwise slice out our position
              else:
                val = val[:-cursleft][:-1] + val[-cursleft:]
                # if we remove the first char we have to decrement cursleft
                cursleft = min(cursleft, len(val))
              break
            continue
          # delete or 0x7f
          if c in ('KEY_DC', '\x7f'):
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
              # restore cursleft
              cursleft += 1
              # ensure we don't go past the len of the val
              cursleft = min(cursleft, len(val))
              break
            continue
          if c == 'KEY_RESIZE':
            height, width = self.scr.getmaxyx()
            break
          # ctrl-z
          if c == '\x1a':
            if len(history) > 0:
              val = history.pop()
              break
            continue
          # move the insert cursor
          if c == 'KEY_LEFT':
            if cursleft < len(val):
              cursleft += 1
              break
            continue
          if c == 'KEY_RIGHT':
            if cursleft > 0:
              cursleft -= 1
              break
            continue
          if c == 'KEY_HOME':
            if cursleft != len(val):
              cursleft = len(val)
              break
            continue
          if c == 'KEY_END':
            if cursleft > 0:
              cursleft = 0
              break
            continue
          # some unhandled key
          if c.startswith('KEY_'):
            continue
          # not input
          if ord(c) < 32 or ord(c) > 126:
            continue
          # input, save the current value in history
          history.append(val)
          # attempt to collect many chars, e.g., "paste"
          self.scr.timeout(CursesScreen.inputtimeout)
          inputstring = c
          try:
            while True:
              try:
                c = self.scr.getkey()
              except curses.error:
                break
              if c.startswith('KEY_') or ord(c) < 32 or ord(c) > 126:
                # push it back into the input and stop
                curses.ungetch(c)
                break
              inputstring += c
          # set input to be blocking again
          finally:
            self.scr.timeout(-1)
          # put the input string where the cursor is
          # append when cursor is max right
          if cursleft == 0:
            val = f'{val}{inputstring}'
          # prepend when cursor is max left
          elif cursleft == len(val):
            val = f'{inputstring}{val}'
          # splice in middle otherwise
          else:
            val = f'{val[:-cursleft]}{inputstring}{val[-cursleft:]}'
          # we took at least 1 char, so break to print it
          break
    finally:
      # hide the cursor
      curses.curs_set(0)
      # reduce cursor movement
      self.scr.leaveok(True)

  def window(self,
            opts: WinOpt,
            title: str='',
            helpkeys: Optional[Tuple[str]]=(),
            returnkeys: Optional[Tuple[str]]=(),
            helpstr: Optional[str]='Help: {@keys@}',
            err: Optional[List[str]]=[],
            body: Optional[List[str]]=[],
            choices: Optional[List[str]]=[],
            footer: Optional[str]='',
            disabled: Optional[List[int]]=[],
            chosen: Optional[List[str]]=[],
            top: Optional[int]=0,
            hpos: Optional[int]=0) -> Tuple[int, int, Union[str, List[str]]]:
    '''
    Display a scrollable choice menu and return the user's selection

    Args:
      opts (WinOpt): Menu options
      title (str): Menu title shown on the first line
      helpkeys (Optional[Tuple[str]]): Keys to recognize as help/exit keys
      returnkeys (Optional[Tuple[str]]): Keys to return, default is enter
      helpstr (Optional[str]): Format string for help display
      body (Optional[List[str]]): Lines shown between title and choices
      choices (Optional[List[str]]): List of choice strings
      disabled (Optional[List[int]]): Indices that cannot be selected
      chosen (Optional[List[str]]): Chosen items (for multi-select)
      top (int): Index of the top visible choice
      hpos (int): Index of the currently highlighted choice

    Returns:
      Tuple[int, int, Union[str, List[str]]]
        - topline (for across-call consistency)
        - activeline
        - input triggering return

    This method is used to print a text menu using :py:attr:`.scr`
      - The title is drawn on the first line
      - An empty line separates the title from the body
      - The body is a list of strings
      - The remaining lines are "choice" lines which can be scrolled

    The current selection at hpos will be highlighted

    Lines which can't be "active" lines and can't be chosen:
      - Empty strings
      - Strings matching an index in disabled

    Returns on either:
      - A key in ``returnkeys`` (or :py:attr:`CursesScreen.returnkeys`)
      - A key in :py:attr:`CursesScreen.cancelkeys`
      - A key in ``helpkeys``, if a corresponding help method not called
    '''
    # validate we have a place to put the cursor
    if not footer and (opts&WinOpt.SHOWCURS):
      # if we want the any key, insert a generic footer
      # otherwise remove SHOWCURS from opts
      if (opts&WinOpt.RETURNANY):
        footer = 'Press the any key to continue . . . '
      else:
        opts ^= WinOpt.SHOWCURS
    # add default help keys
    if not helpkeys and (opts&WinOpt.USEHELP):
      helpkeys = CursesScreen.helpkeys
    # add default return keys
    if not returnkeys and (opts&(WinOpt.RETURNKEY|WinOpt.RETURNMUL)):
      returnkeys = CursesScreen.returnkeys
    # track width to center text
    maxwidth = 0
    if err:
      maxwidth = max(maxwidth,max(len(e) for e in err))
    if body:
      maxwidth =  max(maxwidth,max(len(l) for l in body))
    if choices:
      maxwidth = max(maxwidth, max(len(c) for c in choices))
    if helpkeys and helpstr:
      # put helpkeys into helpstr if @keys@ is in helpstr
      helpstr = helpstr.replace('@keys@', ', '.join(helpkeys))
      maxwidth = max(maxwidth, len(helpstr))
    else:
      # ensure not helpstr if not helpkeys or not helpstr
      helpstr = ''
    # set colors to be used
    disabledcolor = self.disabledcolor
    titlecolor = self.titlecolor
    itemcolor = self.itemcolor
    errorcolor = self.errorcolor
    activecolor = self.activecolor
    # get the dimensions
    height, width = self.scr.getmaxyx()
    # get side buffer
    lshift = max(0, (width-maxwidth)//2)
    # shift buffer for DIAMOND
    if not (opts&WinOpt.TEXTBOX) or (opts&WinOpt.RETURNMUL):
      lshift += 2
    # amount shifted right for long lines
    rshift = [0 for _ in range(len(choices))]
    maxhpos = len(choices) - 1
    # each "section" given a preceding space, if there's a preceding section
    #<title>            1 line
    #<err> len()        n lines
    #<body> len()       n lines
    #<choices> len()    n lines
    #footer             1 line
    #helpstr (if help)  1 line
    # the line for --MORE--
    moreline = -2 if footer or helpstr else -1
    try:
      # restore cursor if we want to show it
      if (opts&WinOpt.SHOWCURS):
        curses.curs_set(2)
        self.scr.leaveok(False)
      while True:
        # clear the screen
        self.scr.erase()
        # add the title
        self.scr.addstr(0, max(0, (width-len(title))//2),
                        title[:width], titlecolor)
        # track the line number we are printing to
        linenum = 2
        # print all lines of err
        if err:
          for line in err:
            if linenum >= height:
              break
            if line:
              self.scr.addstr(linenum, lshift, line[:width-lshift], errorcolor)
            linenum += 1
          linenum += 1
        # print all lines of the body
        if body:
          for line in body:
            if linenum >= height:
              break
            if line:
              self.scr.addstr(linenum, lshift, line[:width-lshift], itemcolor)
            linenum += 1
          # separate body from remainder with another newline
          linenum += 1
        choicestart = linenum
        i = 0
        for i, line in enumerate(choices[top:]):
          # we cannot go beyond height if choices is a long list
          if linenum >= height:
            break
          if line:
            # set the color to active if this is our highlight position
            if not (opts&WinOpt.TEXTBOX) and i+top == hpos and lshift > 1:
              self.scr.insch(linenum, lshift-2, curses.ACS_DIAMOND, activecolor)
            color = disabledcolor \
                      if i+top in disabled \
                    else activecolor \
                      if i+top == hpos and not (opts&WinOpt.TEXTBOX) \
                    else activecolor \
                      if line in chosen \
                    else itemcolor
            self.scr.addstr(linenum, lshift,
                            line[rshift[i+top]:width-lshift+rshift[i+top]-1],
                            color)
          linenum += 1
          if i+top == len(choices)-1:
            pass
          elif footer and helpstr:
            if linenum + 4 >= height:
              break
          elif footer or helpstr:
            if linenum + 2 >= height:
              break
          elif linenum == height+moreline:
            break
        nchoicelines = i
        if footer:
          linenum += 1
          if linenum < height:
            self.scr.addstr(linenum, max(0, (width-len(footer))//2),
                            footer[:width], itemcolor)
            cursy, cursx = self.scr.getyx()
          else:
            cursy = height
          linenum += 1
        if helpstr:
          linenum += 1
          if linenum < height:
            self.scr.addstr(linenum, max(0, (width-len(helpstr))//2),
                            helpstr[:width], itemcolor)
        if i+top < len(choices)-1:
          self.scr.addstr(height+moreline, 0,
                          '--More--'[:width], self.standoutcolor)
        if (opts&WinOpt.SHOWCURS) and cursy < height:
          self.scr.move(cursy, cursx)
        self.scr.refresh()
        # we are going to immediately return without getting input
        if (opts&WinOpt.RETURNIMM):
          return
        # while we don't need to redraw the screen
        while True:
          # get our response, reset the cursor and process the response
          c = self.scr.getkey()
          if (opts&WinOpt.RETURNANY):
            return top, hpos, c
          # the direction we are moving (up=-1, neither=0, down=1)
          direction = 0
          # the key is in helpkeys
          if c in helpkeys:
            try:
              # hide the cursor if we used it
              if (opts&WinOpt.SHOWCURS):
                curses.curs_set(0)
                self.scr.leaveok(True)
              frame_info = inspect.stack()[1]
              inst = frame_info.frame.f_locals.get('self')
              helpfn = None
              # we were called by a class
              if inst is not None:
                # the class has a help_{function_name} method
                helpfn = getattr(inst, f'help_{frame_info.function}', None)
              # call their help function and forward their title
              if callable(helpfn):
                helpfn(title=title)
                # the screen was resized, reset shifts/sizes
                if (height, width) != self.scr.getmaxyx():
                  rshift = [0 for _ in rshift]
                  height, width = self.scr.getmaxyx()
                  lshift = max(0, (width-maxwidth)//2)
                  if (opts&WinOpt.RETURNMUL):
                    lshift += 2
                # we need to redraw the screen to wipe the helpfn
                break
              else:
                return top, hpos, c
            finally:
              # restore cursor if we want to show it
              if (opts&WinOpt.SHOWCURS):
                curses.curs_set(2)
                self.scr.leaveok(False)
              # delete vars to ensure the references go away
              del frame_info, inst, helpfn
          # delete key
          elif c in ('KEY_DC', '\x7f') and (opts&WinOpt.RETURNDEL):
            return top, hpos, 'KEY_DC'
          # return key
          elif (opts&(WinOpt.RETURNKEY|WinOpt.RETURNMUL)) and c in returnkeys:
            if (opts&WinOpt.RETURNMUL):
              # for multi-select we return chosen on hpos == 0
              # the first choice (hpos==0) should be a variation of 'confirm'
              if hpos == 0:
                return top, hpos, chosen
              # otherwise we add the choice to chosen or remove it (toggle)
              if choices[hpos] in chosen:
                del chosen[chosen.index(choices[hpos])]
              else:
                chosen.append(choices[hpos])
            else:
              # if not multi-select we just return hpos (and the return char)
              return top, hpos, c
          # return on cancel key
          elif c in CursesScreen.cancelkeys:
            return top, hpos, c
          # go to the top
          elif c == 'KEY_HOME':
            # let the home key also reset all rshifts
            rshift = [0 for _ in rshift]
            # if we actually move change hpos and set direction
            if hpos > 0:
              hpos = 0
              direction = -1
            # either way, we at least may have changed rshift
            break
          # go to the bottom
          elif c == 'KEY_END' and hpos < maxhpos:
            hpos = maxhpos
            direction = 1
            break
          # go up
          elif c == 'KEY_UP' and hpos > 0:
            hpos -= 1
            direction = -1
            break
          # go down
          elif c == 'KEY_DOWN' and hpos < maxhpos:
            hpos += 1
            direction = 1
            break
          # jump up
          elif c == 'KEY_PPAGE' and hpos > 0:
            hpos -= nchoicelines-2
            if hpos < 0:
              hpos = 0
            direction = -1
            break
          # jump down
          elif c == 'KEY_NPAGE' and hpos < maxhpos:
            hpos += nchoicelines-2
            if hpos > maxhpos:
              hpos = maxhpos
            direction = 1
            break
          # move right
          elif c == 'KEY_RIGHT' and choices:
            if (opts&WinOpt.TEXTBOX):
              # scroll the entire pane together
              if lshift+maxwidth-rshift[0] >= width:
                rshift = [shmt+1 for shmt in rshift]
                break
            elif lshift+len(choices[hpos][rshift[hpos]:]) > width:
              # scroll the line
              rshift[hpos] += 1
              break
          elif c == 'KEY_LEFT' and choices and rshift[hpos] > 0:
            if (opts&WinOpt.TEXTBOX):
              rshift = [shmt-1 for shmt in rshift]
            else:
              rshift[hpos] -= 1
            break
          elif c == 'KEY_RESIZE':
            # reset rshift on resizes
            rshift = [0 for _ in rshift]
            # get new dimensions
            height, width = self.scr.getmaxyx()
            lshift = max(0, (width-maxwidth)//2)
            if (opts&WinOpt.RETURNMUL):
              lshift += 2
            break
        # verify hpos and topline
        if direction != 0:
          # ensure hpos lands on something valid
          while hpos >= 0 and hpos <= maxhpos and \
                (hpos in disabled or not choices[hpos]):
            hpos += direction
          # if we go OOB reverse and move to the nearest choice
          if hpos < 0 or hpos > maxhpos:
            direction = -direction
            hpos += direction
            while hpos >= 0 and hpos <= maxhpos and \
                  (hpos in disabled or not choices[hpos]):
              hpos += direction
            direction = -direction
          # final gaurd against OOB hpos
          if hpos < 0:
            hpos = 0
          elif hpos > maxhpos:
            hpos = maxhpos
          if (opts&WinOpt.TEXTBOX):
            top = hpos
            # cap downward movement
            if maxhpos - top < nchoicelines:
              top = hpos = maxhpos - nchoicelines
        if hpos - top < 0:
          top = hpos
        elif choicestart + hpos - top + (2 if helpstr else 1) >= height:
          top = choicestart + hpos - height + 1 + (2 if helpstr else 1)
    finally:
      # hide the cursor if we used it
      if (opts&WinOpt.SHOWCURS):
        curses.curs_set(0)
        self.scr.leaveok(True)

  def getdir(self,
            title: str,
            prompt: Optional[str]='Select a directory',
            path: Optional[Path]=None,
            allownew: Optional[bool]=True) -> Optional[str]:
    '''
    Show a directory selection menu and return the chosen path

    Args:
      title (str): Window title
      prompt (str): Prompt shown to the user
      path (Optional[pathlib.Path]): Starting directory (default is pwd)
      allownew (Optional[bool]): Whether the directory must already exist

    Returns:
      Optional[str]: Selected directory as a string, or None if cancelled
    '''
    # the path starts at the current working directory if not provided
    if path is None:
      path = Path.cwd()
    body = [prompt, '', f'Dir: {path}', '']
    top, hpos = 0, 0
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
      top, hpos, c = self.window(
        WinOpt.RETURNKEY,
        title=title,
        body=body,
        disabled=[names.index('\b\bChange directory:')],
        choices=names,
        top=top,
        hpos=hpos,
      )
      # allow to return without opening a file:
      if c in CursesScreen.cancelkeys:
        return None
      # choice is Select
      if hpos == 0:
        return f'{path}'
      # choice is Make subdirectory
      if allownew and hpos == 1:
        dirname = self.getinput(title, 'Enter new directory name:')
        if dirname is None:
          continue
        try:
          os.mkdir(path / dirname)
          return f'{path / dirname}'
        except FileExistsError:
          if os.path.isdir(path / dirname):
            self.window(
              WinOpt.SHOWCURS|WinOpt.RETURNANY,
              title=title,
              err=f'Directory {dirname} exists',
            )
          else:
            self.window(
              WinOpt.SHOWCURS|WinOpt.RETURNANY,
              title=title,
              err=f'Directory {dirname} is a file',
            )
        except PermissionError:
          self.window(
            WinOpt.SHOWCURS|WinOpt.RETURNANY,
            title=title,
            err=f'No permission to create {dirname}',
          )
        except Exception as e:
          self.window(
            WinOpt.SHOWCURS|WinOpt.RETURNANY,
            title=title,
            err=[m.strip() for m in re.split(r'[:\n]+', str(e))],
          )
      # we selected to go up
      elif names[hpos] == '..':
        path = path.parent
        body[-2] = f'Dir: {path}'
        hpos = 0
        top = 0
      # our selection is a subdirectory
      else:
        path = path / names[hpos]
        body[-2] = f'Dir: {path}'
        hpos = 0
        top = 0

  def getfile(self,
              title: str,
              prompt: Optional[str]='Select a file',
              path: Optional[Path]=None,
              perm: Optional[Literal[os.R_OK, os.W_OK, os.X_OK]]=os.R_OK,
              filere: Optional[str]='') -> Optional[str]:
    '''
    Show a file-selection menu and return the chosen filename

    Args:
      title (str): Window title
      prompt (str): Prompt shown to the user
      path (Optional[pathlib.Path]): Starting directory (default is pwd)
      perm (int): Optional additional permissions beyond :py:data:`os.R_OK`
      filere (str): Regex to filter filenames available to be chosen

    Returns:
      Optional[str]: Selected filename as a string, or None if cancelled
    '''
    # the path starts at the current working directory if not provided
    if path is None:
      path=Path.cwd()
    # the permissions should at least have R_OK
    if (perm&os.R_OK) == 0:
      perm |= os.R_OK
    # compile the fileregex (the empty string matches all files)
    try:
      match = re.compile(filere)
    except Exception as e:
      self.window(
        WinOpt.SHOWCURS|WinOpt.RETURNANY,
        title=title,
        body=['Exception during re.compile'],
        err=[m.strip() for m in re.split(r'[:\n]}',str(e))],
      )
      return None
    body = [prompt, '', f'Path: {path}', '']
    top = 0
    hpos = 1
    # when we move to a new directory update the body text and reset pos
    while True:
      # get the sorted contents of the directory
      names = sorted([name for name in path.iterdir()])
      # only keep names we have (at least) read permission for
      names = [name for name in names if os.access(name, os.R_OK)]
      # keep files with perm and directories with X_OK
      names = [name for name in names if \
                (name.is_file() and os.access(name, perm)) or \
                (name.is_dir() and os.access(name, os.X_OK))]
      # keep only directories (not file) and files which match the filere
      names = [name for name in names if not name.is_file() or \
                match.match(str(name))]
      # squash to strings and reorder
      # directories before files, directories end with os.path.sep
      names = [str(name.name)+os.path.sep \
                for name in names if name.is_dir()] + \
              [''] + \
              [str(name.name) for name in names if name.is_file()]
      # give an option to go up a level unless we are at the root
      if path.parents:
        names.insert(0, '..')
      names = ['\b\bChange path:'] + names
      disabled = [0, names.index('')]
      names[disabled[-1]] = '\b\bSelect file:'
      # get the response
      top, hpos, c = self.window(
        WinOpt.RETURNKEY,
        title=title,
        body=body,
        disabled=disabled,
        choices=names,
        top=top,
        hpos=hpos,
      )
      # allow to return without opening a file:
      if c in CursesScreen.cancelkeys:
        return None
      # we selected to go up
      if names[hpos] == '..':
        path = path.parent
        body[-2] = f'Path: {path}'
        hpos = 1
        top = 0
      # our selection is a subdirectory
      elif os.path.isdir(path / names[hpos]):
        path = path / names[hpos]
        body[-2] = f'Path: {path}'
        hpos = 1
        top = 0
      # our selection was a file
      else:
        return f'{path / names[hpos]}'

  def drawsplitpane(self,
                    lhs: List[str],
                    lpos: List[int],
                    rhs: List[str],
                    rpos: List[int],
                    highlight: bool,
                    paneshmt: int,
                    ltitle: str,
                    rtitle: str,
                    linenums: bool,
                    helpstr: Optional[str]='') -> None:
    '''
    The screen is divided vertically into 2 segments

    lhs and rhs are lists of strings with titles ltitle and rtitle

    lpos and rpos determines which row/col is the top left of each pane
      - {l,r}pos[0] = first row, [1] = first col
      - last row = {l,r}pos[0] + height - 1


    The division is shifted by paneshmt
      - where 0 is vertical bar at width/2 -- neg/pos shifts left/right

    With linenums=True, a line number can be printed to the left of a line
      - (if {l,r}pos[1] is negative)

    The screen is cleared, strings added to screen, then refreshed
    '''
    infocolor = self.titlecolor
    # clear the screen
    self.scr.erase()
    # the current height and width (will change if window is resized)
    height, width = self.scr.getmaxyx()
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
      lenr = 0
      # width chars given for lhs
      lenl = width-1
    # lhs is shifted out of view
    # +|------------+
    elif middle < 1:
      printside = lambda side: side==rhs
      rstart = 0
      lenr = width-1
      lenl = 0
    # have both left and right panes
    else:
      # set drawvline to not None here
      drawvline = False
      printside = lambda side: True
      # middle is vbar, rstart=vbar+1, lenl=vbar-1
      rstart = middle + 1
      lenr = width - rstart - 1
      lenl = middle
    ltitle = ltitle[:lenl]
    rtitle = rtitle[:lenr]
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
        color = self.activecolor
      else:
        color = self.itemcolor
      if helpstr:
        if i+lpos[0] == -3 or i+lpos[0] == len(lhs)+1:
          if i+rpos[0] == -3 or i+rpos[0]==len(rhs)+1:
            lshift = max(0, middle - len(helpstr)//2)
          else:
            lshift = max(0, middle - len(helpstr))
          self.scr.addstr(i, lshift, helpstr, self.activecolor)
          helpstr = ''
        elif i+rpos[0] == -3 or i+rpos[0] == len(rhs)+1:
          self.scr.addstr(i, rstart, helpstr, self.activecolor)
          helpstr = ''
      # draw lhs
      if lenl > 0:
        if i+lpos[0] == -2:
          self.scr.hline(i, 0, curses.ACS_HLINE, lenl, self.standoutcolor)
        elif i+lpos[0] == -1:
          self.scr.addnstr(i, 1, ltitle, len(ltitle), infocolor)
          padlen = len(ltitle)
          if padlen+2 < lenl:
            pad = ' '*(lenl-padlen-2)
            self.scr.addnstr(i, padlen+2, pad, len(pad), self.bordercolor)
        elif i+lpos[0] == len(lhs):
          self.scr.hline(i, 0, curses.ACS_HLINE, lenl, self.standoutcolor)
        elif haveline(i+lpos[0], lhs):
          if lpos[1] < 0:
            lindex = f'{lpos[0]+i+1:{lilen}d}'[lpos[1]:]
            if linenums:
              self.scr.addnstr(i, 0, lindex, lenl, infocolor)
            lindex = len(lindex)
            if lenl-lindex > 0:
              self.scr.addnstr(i, lindex, lhs[lpos[0]+i][:lenl-lindex],
                          lenl-lindex, color)
          else:
            self.scr.addnstr(i, 0,
                        lhs[lpos[0]+i][lpos[1]:lpos[1]+lenl],
                        lenl, color)
        elif drawvline is not None:
          drawvline = False
        if drawvline:
          self.scr.addch(i, middle, curses.ACS_VLINE, self.standoutcolor)
      # draw rhs
      if lenr > 0:
        if drawvline is not None and not drawvline:
          drawvline = True
        if i+rpos[0] == -2:
          self.scr.hline(i, rstart, curses.ACS_HLINE, lenr, self.standoutcolor)
        elif i+rpos[0] == -1:
          padlen = len(rtitle)
          if padlen+1 < lenr:
            pad = ' '*(lenr-padlen-1)
            self.scr.addnstr(i, rstart, pad, len(pad), self.bordercolor)
          self.scr.addnstr(i, width-len(rtitle)-1,
                      rtitle, len(rtitle), infocolor)
        elif i+rpos[0] == len(rhs):
          self.scr.hline(i, rstart, curses.ACS_HLINE, lenr, self.standoutcolor)
        elif haveline(i+rpos[0], rhs):
          if rpos[1] < 0:
            rindex = f'{rpos[0]+i+1:{rilen}d}'[rpos[1]:]
            if linenums:
              self.scr.addnstr(i, rstart, rindex, lenr, infocolor)
            rindex = len(rindex)
            if rindex < lenr:
              self.scr.addnstr(i, rstart+rindex,
                              rhs[rpos[0]+i][:lenr-rindex],
                              lenr-rindex, color)
          else:
            self.scr.addnstr(i, rstart,
                            rhs[rpos[0]+i][rpos[1]:rpos[1]+lenr],
                            lenr, color)
        elif drawvline is not None:
          drawvline = False
        if drawvline:
          self.scr.addch(i, middle, curses.ACS_VLINE, self.standoutcolor)
    self.scr.refresh()

  def help_diffwindow(self, title: str) -> None:
    '''
    help_diffwindow displays an infowindow with diffwindow's docstr
    '''
    self.window(
      WinOpt.RETURNKEY|WinOpt.TEXTBOX,
      title=f'{title} Help',
      choices=getdoc(self.diffwindow).strip('\n').split('\n'),
    )

  def diffwindow(self,
                args: Tuple[str, str, List[str], str, List[str]]) -> None:
    '''
    Diff Window
    -----------

    Commands available while the diff view is active:
      - Toggle match highlighting:  d D
      - Toggle left/right pane lock:  <SPACE>
      - Toggle left/right pane scrolling:  <TAB>
      - Move pane separator left/right:  + -
      - Reset pane separator shift:  =
      - Toggle line-number printing:  n N
      - Quit:  <ESC> q Q
    '''

    helpkeys = CursesScreen.helpkeys
    helpstr = 'Help: {@keys@}'.replace('@keys@', ', '.join(helpkeys))

    # diffwindow args = title, ltitle, lhs, rtitle, rhs
    # ignore empty lines, trailing whitespace, and substitute tabs in lhs/rhs
    title = args[0]
    ltitle = args[1]
    lhs = [line.rstrip().replace('\t',' '*CursesScreen.tabsize) \
                                                for line in args[2] \
                                                if line.strip() != '']
    if not lhs:
      ltitle += ' (no contents)'
    rtitle = args[3]
    rhs = [line.rstrip().replace('\t',' '*CursesScreen.tabsize) \
                                                for line in args[4] \
                                                if line.strip() != '']
    if not rhs:
      rtitle += ' (no contents)'

    # get column length for lhs and rhs (max of any element)
    lwidth = max(len(row) for row in lhs) if lhs else 0
    rwidth = max(len(row) for row in rhs) if rhs else 0
    # track the height/width
    height, width = self.scr.getmaxyx()
    # track top left 'coordinate' of the text in the lists
    # the l/rpos is the starting row + col to display
    # -2 for the 2 title bar rows
    lpos = [-2,0] # lpos[0] is starting row
    rpos = [-2,0] # rpos[1] is starting col
    # set limits for pos
    # don't set pos row less then -height
    # don't set pos col less than -4 (allows 3 digit num)
    # 1 row remains on screen (at bottom)
    minpos = [-height+1, -4]
    # max pos prints 1 row of a pane (at top), right col of line
    maxlpos = (len(lhs)-1, lwidth-1)
    maxrpos = (len(rhs)-1, rwidth-1)
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
                        ((key == 'KEY_HOME' or \
                          key == 'KEY_PPAGE' or \
                          key == 'KEY_UP') and \
                  (scroll('left') and lpos[0] > minpos[0]) or \
                  (scroll('right') and rpos[0] > minpos[0])) or \
                        ((key == 'KEY_END' or \
                          key == 'KEY_NPAGE' or \
                          key == 'KEY_DOWN') and \
                  (scroll('left') and lpos[0] < maxlpos[0]) or \
                  (scroll('right') and rpos[0] < maxrpos[0])) or \
                        (key == 'KEY_LEFT' and \
                  (scroll('left') and lpos[1] > minpos[1]) or \
                  (scroll('right') and rpos[1] > minpos[1])) or \
                        (key == 'KEY_RIGHT' and \
                  (scroll('left') and lpos[1] < maxlpos[1]) or \
                  (scroll('right') and rpos[1] < maxrpos[1]))
    # toggle for whether to highlight matching lines
    highlight = True
    # toggle for whether to print line numbers
    linenums = True
    # shift amount for pane boundary, division between lhs/rhs views
    paneshmt = 0
    c = ''
    # inject a resize event into the input stream
    # our first getch will be resize which triggers a "repaint"
    curses.ungetch(curses.KEY_RESIZE)
    while True:
      c = self.scr.getkey()
      if c in CursesScreen.cancelkeys:
        break
      # handle keys that don't trigger repainting first
      # the space key toggles independent scrolling
      if c == ' ':
        singlescroll = not singlescroll
        continue
      # the tab key toggles whether lhs or rhs is the actively scrolled tab
      elif c == '\t':
        leftscroll = not leftscroll
        continue
      # help
      if c in helpkeys:
        self.help_diffwindow(title)
      # a resize event
      elif c == 'KEY_RESIZE':
        height, width = self.scr.getmaxyx()
        minpos[0] = -height+1
        # ensure we didn't go past minpos
        if lpos[0] < minpos[0]:
          lpos[0] = minpos[0]
        if rpos[0] < minpos[0]:
          rpos[0] = minpos[0]
      # toggle line match highlight with [dD] (for diff)
      elif c in ('D', 'd'):
        highlight = not highlight
      # toggle printing line numbers with [nN]
      elif c in ('N', 'n'):
        linenums = not linenums
      # plus key to shift pane separator right
      elif c == '+' and width//2+paneshmt < width-2:
        paneshmt += 1
      # minus key to shift pane separator left
      elif c == '-' and width//2+paneshmt > 0:
        paneshmt -= 1
      # equal key to reset pane shift
      elif c == '=' and paneshmt != 0:
        paneshmt = 0
      elif willscroll(c):
        # go to top
        if c == 'KEY_HOME':
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
        elif c == 'KEY_END':
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
        elif c == 'KEY_PPAGE':
          if scroll('left'):
            lpos[0] = max(lpos[0]-height-3, minpos[0])
          if scroll('right'):
            rpos[0] = max(rpos[0]-height-3, minpos[0])
        # page down
        elif c == 'KEY_NPAGE':
          if scroll('left') and height < len(lhs):
            lpos[0] = min(lpos[0]+height-3, maxlpos[0])
          if scroll('right') and height < len(rhs):
            rpos[0] = min(rpos[0]+height-3, maxrpos[0])
        # scroll up
        elif c == 'KEY_UP':
          if scroll('left') and lpos[0] > minpos[0]:
            lpos[0] -= 1
          if scroll('right') and rpos[0] > minpos[0]:
            rpos[0] -= 1
        # scroll down
        elif c == 'KEY_DOWN':
          if scroll('left') and lpos[0] < maxlpos[0]:
            lpos[0] += 1
          if scroll('right') and rpos[0] < maxrpos[0]:
            rpos[0] += 1
        # scroll left
        elif c == 'KEY_LEFT':
          if scroll('left') and lpos[1] > minpos[1]:
            lpos[1] -= 1
          if scroll('right') and rpos[1] > minpos[1]:
            rpos[1] -= 1
        # scroll right
        elif c == 'KEY_RIGHT':
          if scroll('left') and lpos[1] < maxlpos[1]:
            lpos[1] += 1
          if scroll('right') and rpos[1] < maxrpos[1]:
            rpos[1] += 1
      # if we didn't match a condition above then don't repaint
      else:
        continue
      self.drawsplitpane(lhs, lpos, rhs, rpos, highlight, paneshmt,
                          ltitle, rtitle, linenums, helpstr)
