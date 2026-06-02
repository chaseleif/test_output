import curses, os, re, shlex, shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from .config import CSTesterConfig
from .utils import collapsenumrange
from .win import CursesScreen, WinOpt

# any value is either a string or None
# a variable value is either just the optional string or a tuple for dict
# for a dict we need {key:val}, so we have a key and an optional str
VarVal = Union[Optional[str], Tuple[str, Optional[str]]]
# the attributes of the CSTesterConfig that we can return
AttrVal = Union[str, List[str], Dict[str, str]]
# for __add__ we have a tuple of str(attr) and a val
KeyVal = Tuple[str, VarVal]

class ConfigManager:
  '''
  Utility class providing a managed interface
  to the :py:class:`.CSTesterConfig` dataclass
  '''
  def __init__(self, scr: 'CursesScreen', configfile: Optional[str]='') -> None:
    '''
    Args:
      scr (CursesScreen): The running curses screen which
        provides window functions to display windows and accept input
      configfile (str, Optional): Path to a saved YAML configuration file
    '''
    #: The active :py:class:`.CursesScreen` object
    self.scr = scr
    #: Our :py:class:`.CSTesterConfig`, the dataclass holding configuration
    self.conf = None
    if os.path.isfile(configfile):
      try:
        self.conf = CSTesterConfig.from_yaml(configfile)
      except:
        pass
    if self.conf is None:
      self.conf = CSTesterConfig()
    #: Names of :py:attr:`.conf` attributes that are regular expressions
    self.regexes = ('groupre_str',
                    'zipinclude_strs',
                    'zipexclude_strs',
                    'freezefiles',
                    'cleanfiles',
                    'searchstrs',
                    'searchfiles',
                    )
    #: Names of :py:attr:`.conf` attributes that are directories
    self.dirs = ('phasedir', 'casedir', 'expdir', 'templatedir')
    #: Names of :py:attr:`.conf` attributes that are files
    #: (including an optional file-filter regex to use)
    self.files = { 'phasezip':'.*\\.[Zz][Ii][Pp]', 'keyfile':'' }
    #: Names of :py:attr:`.conf` attributes that are number/range lists
    self.numranges = ('include', 'exclude')
    #: Names of :py:attr:`.conf` attributes that contain executable commands
    self.commands = ('groupcmd', 'prepcmds')
    #: Names of :py:attr:`.conf` attributes which can have empty strings
    self.emptyok = ('caseext', 'expext', 'zipinclude_strs')
    #: Dictionary of prompts to use in :py:meth:`.modifyconf`
    self.prompts = {
        'saveconfig':'Enter filename for output YAML:',
        'phasedir':'Select the phase submission directory',
        'phasezip':'Select the phase submission zip file',
        'keyfile':'Select the keyfile to aid extraction',
        'groupre_str':'Regex to extract group number from group zip:',
        'zipexclude_strs':('Regex for files to not extract',
                          'Regex to match files:'),
        'zipinclude_strs':('Regexes for files wanted and their location',
                          'Regex to match files:',
                          'Where \"@KEY@\" files go relative to group root:'),
        'include':'Group(s) to only include:',
        'exclude':'Group(s) to exclude:',
        'freezefiles':('Regex for files to freeze for diff',
                      'Regex to match files:'),
        'cleanfiles':('Regex for for files to remove:',
                      'Regex to match files:'),
        'casedir':'Select the input cases directory',
        'caseext':'Input cases\' file-extension:',
        'expdir':'Select the expected output directory',
        'expext':'Expected outputs\' file-extension:',
        'templatedir':'Select the template directory',
        'groupcmd':'Command to run within group directories:',
        'testcmd':'Command to test program, e.g., \'./obj/mcc @case@\':',
        'prepcmds':('Commands to prepare submission for testing:',
                    'Command to run next:'),
        'readmename':'Enter the README filename:',
        'searchstrs':('Regex of strings to search for within files',
                      'Regex of string to search for:'),
        'searchfiles':('Regex for files to search for strings within',
                      'Regex to match files:'),
        }

  def has(self, attr: str) -> bool:
    '''
    Check whether :py:attr:`.conf` has attribute ``attr``

    Args:
      attr (str): Attribute name to check

    Returns:
      bool: True if :py:attr:`.conf`.``attr`` exists
    '''
    return hasattr(self.conf, attr)

  def isset(self, attr: str) -> bool:
    '''
    Check whether :py:attr:`.conf`.``attr`` is set (non-empty)

    Args:
      attr (str): Attibute name to check

    Returns:
      bool: True if the :py:attr:`.conf`.``attr`` is non-empty
    '''
    if getattr(self.conf, attr):
      return True
    return False

  def resetattr(self, attr: str) -> None:
    '''
    Reset :py:attr:`.conf`.``attr`` to its default value

    Args:
      attr (str): Attribute name to reset
    '''
    setattr(self.conf, attr, self.conf.default_value(attr))

  def get(self, attr: str) -> AttrVal:
    '''
    Get :py:attr:`.conf`.``attr``

    Args:
      attr (str): Attribute name to retrieve

    Returns:
      :type str, list of str, or dict[str, str]: :py:attr:`.conf`.``attr``

    Raises:
      AttributeError:
        if :py:attr:`.conf`.``attr`` doesn't exist
    '''
    if hasattr(self.conf, attr):
      return getattr(self.conf, attr)
    raise AttributeError(f'\'{type(self).__name__}\' object ' + \
                          f'has no attribute \'{attr}\'')

  def set(self, attr: str, val: AttrVal) -> None:
    '''
    Set :py:attr:`.conf`.``attr`` to ``val``

    Args:
      attr (str): Attribute name to set
      val :type str, list of str, or dict[str, str]: Value to assign
    '''
    setattr(self.conf, attr, val)

  def __getattr__(self, attr: str) -> AttrVal:
    '''
    Forward member requests from the dot operator to :py:attr:`.conf`

    Args:
      attr (str): Attribute name

    Returns:
      :type str, list of str, or dict[str, str]: :py:attr:`.conf`.``attr``
    '''
    return self.get(attr)

  def load(self, filename: str = '') -> None:
    '''
    Create an instance of :py:class:`.CSTesterConfig`
    from a YAML configuration file

    Args:
      filename (str): Path to YAML file

    Sets :py:attr:`.conf`
    '''
    title = 'Load configuration'
    if not filename:
      filename = self.scr.getfile(title, 'Select yaml:', Path.cwd(),
                                  filere='.*\\.[Yy][Aa][Mm][Ll]$')
    if not filename:
      return
    try:
      self.conf = CSTesterConfig.from_yaml(filename)
      self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                      title=title,
                      body=[f'Configuration loaded from \"{filename}\"'])
    except Exception as e:
      self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                      title=title,
                      body=[f'Unable to load from \"{filename}\"'],
                      err=[m.strip() for m in re.split(r'[:\n]+',str(e))])

  def save(self) -> None:
    '''
    Save the configuration of :py:attr:`.conf` to a YAML file
    '''
    title = 'Save configuration'
    filename = self.scr.getinput(title, 'Save to:')
    if filename is None:
      return
    filename = os.path.splitext(filename)
    if not filename[-1] or filename[-1].lower() == '.yaml':
      filename = f'{filename[0]}.yaml'
    else:
      filename = ''.join(filename) + '.yaml'
    conf = self.conf.to_yaml()
    if os.path.isfile(filename):
      _, _, c = self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                                title=title,
                                err=[f'File \"{filename}\" already exists'],
                                footer='Overwrite file? [y/N] ')
      # if c is not Y or y
      if c not in ['Y','y']:
        self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                        title=title,
                        err=[f'Save aborted: not overwriting \"{filename}\"'])
        return
    try:
      with open(filename, 'w') as configfile:
        configfile.write(conf)
      self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                      title=title,
                      body=[f'Configuration saved to \"{filename}\"'])
    except Exception as e:
      self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                      title=title,
                      body=[f'Save failure: unable to write \"{filename}\"'],
                      err=[m.strip() for m in re.split(r'[:\n]+',str(e))])

  def verifiedregex(self, val: VarVal) -> VarVal:
    '''
    Validate ``val`` using :py:func:`re.compile`

    Args:
      val :type Optional[str], or Tuple[str, Optional[str]]:
        Input value

    Returns:
      Optional[str]: Verified regex string or None
    '''
    def badregex(e: str) -> None:
      self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                      title='Regex compile verification',
                      body=['Exception during re.compile'],
                      err=[m.strip() for m in re.split(r'[:\n]+',e)])
    # reject empty string as well as None for regexes
    # when VarVal is a tuple, index 0 is the key and index 1 is the value
    # this allows to use rhs when lhs, i.e., if (regex) then (value)
    if isinstance(val, tuple):
      if val[0]:
        try:
          re.compile(val[0])
          return val
        except re.error as e:
          badregex(str(e))
    elif val:
      try:
        re.compile(val)
        return val
      except re.error as e:
        badregex(str(e))

  def verifiednumrange(self, val: Optional[str]) -> Optional[str]:
    '''
    Validate that ``val`` is a valid number/range list

    Args:
      val (Optional[str]): Input string

    Returns:
      Optional[str]: verified number/range list string or None
    '''
    if not val:
      return None
    val = collapsenumrange(val)
    if val:
      return val
    self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                    title='Number-range list verification',
                    err=['Number-range lists can be:',
                          '- a single value',
                          '- a comma-seperated list of values',
                          'Each value can be:',
                          '- single number',
                          '- valid range, e.g., 2-5'])

  def verifiedcommand(self, cmd: Optional[str]) -> Optional[str]:
    '''
    Validate that ``cmd`` is a valid command

    Args:
      cmd (Optional[str]): Command string

    Returns:
      Optional[str]: Verified command string or None
    '''
    if not cmd:
      return None
    cmd = shlex.split(cmd)
    # shell built-in
    if shutil.which(cmd[0]) is not None:
      return shlex.join(cmd)
    # executable file
    if os.path.isfile(cmd[0]) and os.access(cmd[0], os.R_OK|os.X_OK):
      return shlex.join(cmd)
    self.scr.window(WinOpt.SHOWCURS|WinOpt.RETURNANY,
                    title='Command verification',
                    err=[f'Could not verify command \"{shlex.join(cmd)}\"',
                          'Checked shell built-ins',
                          'Checked if it is an executable file'])
    return None

  def verifyval(self, key: str, val: VarVal) -> VarVal:
    '''
    Dispatch verification for a field based on its key

    Args:
      key (str): Configuration key
      val :type Optional[str], or Tuple[str, Optional[str]]:
        Value to verify

    Returns:
      :type Optional[str], or Tuple[str, Optional[str]]: Verified value
    '''
    if key in self.regexes:
      return self.verifiedregex(val)
    elif key in self.numranges:
      return self.verifiednumrange(val)
    elif key in self.commands:
      return self.verifiedcommand(val)
    return val

  def __add__(self, keyval: KeyVal) -> 'ConfigManager':
    '''
    Add a key/value pair to the configuration using the + operator

    Args:
      keyval :type Tuple[str, [Optional[str], or Tuple[str, Optional[str]]]]:
        Tuple or mapping with key and value

    Returns:
      ConfigManager: **self** (after modification)
    '''
    key = keyval[0]
    val = self.verifyval(key, keyval[1])
    if val is None:
      pass
    elif isinstance(getattr(self.conf, key), dict):
      if val[1] or key in self.emptyok:
        getattr(self.conf, key).update({val[0]:val[1]})
    elif not val and key not in self.emptyok:
      pass
    elif isinstance(getattr(self.conf, key), list):
      getattr(self.conf, key).append(val)
    else:
      setattr(self.conf, key, val)
    return self

  def modifylist(self, key: str, title: str) -> None:
    '''
    Prompt the user to obtain and set a list value for a key

    Args:
      key (str): Configuration key
      title (str): Display title for prompts/menus
    '''
    body = ['Add new or modify or remove existing',
            '',
            self.prompts[key][0],
            '']
    prompt = self.prompts[key][1]
    top, hpos = 0, 0
    while True:
      top, hpos, c = self.scr.window(WinOpt.RETURNKEY|WinOpt.RETURNDEL,
                                      title=title, body=body,
                                      choices=['Finished', 'Add new',''] + \
                                      getattr(self.conf, key),
                                      top=top, hpos=hpos)
      if c == 'KEY_DC':
        if hpos > 2:
          del getattr(self.conf, key)[hpos-3]
          hpos -= 1
          if hpos == 2:
            hpos = 1
      elif c in CursesScreen.cancelkeys or hpos == 0:
        return
      elif hpos == 1:
        self += (key, self.scr.getinput(title, prompt))
      else:
        val = getattr(self.conf, key)[hpos-3]
        val = self.scr.getinput(title, prompt, val)
        if val is None:
          pass
        elif not val:
          del getattr(self.conf, key)[hpos-3]
          if hpos == len(getattr(self.conf, key)) + 3:
            hpos -= 1
        else:
          val = self.verifyval(key, val)
          if val is not None:
            getattr(self.conf, key)[hpos-3] = val

  def modifydict(self, key: str, title: str) -> None:
    '''
    Prompt the user to obtain and set a dict value for a key

    Args:
      key (str): Configuration key
      title (str): Display title for prompts/menus
    '''
    keybody = ['Add new or modify or remove existing',
              '',
              self.prompts[key][0],
              '']
    top, hpos = 0, 0
    keyprompt = self.prompts[key][1]
    while True:
      top, hpos, c = self.scr.window(WinOpt.RETURNKEY|WinOpt.RETURNDEL,
                                      title=title, body=keybody,
                                      choices=['Finished', 'Add new',''] + \
                                              [f'\"{k}\" : \"{v}\"' for k,v in
                                              getattr(self.conf, key).items()],
                                      top=top, hpos=hpos)
      if c == 'KEY_DC':
        if hpos > 2:
          k = list(getattr(self.conf, key).keys())[hpos-3]
          del getattr(self.conf, key)[k]
          if not self.isset(key):
            hpos = 1
      elif c in CursesScreen.cancelkeys or hpos == 0:
        return
      elif hpos == 1:
        k = self.scr.getinput(title, keyprompt)
        k = self.verifyval(key, k)
        if k:
          valprompt = self.prompts[key][2].replace('@KEY@', k)
          v = self.scr.getinput(title, valprompt)
          self += (key, (k,v))
      else:
        # original key and val
        ok, ov = list(getattr(self.conf, key).items())[hpos-3]
        k = self.scr.getinput(title, keyprompt, ok)
        if k is None:
          pass
        # empty string, remove the item
        elif not k:
          del getattr(self.conf, key)[ok]
          if hpos == len(getattr(self.conf, key)) + 3:
            hpos -= 1
        else:
          k = self.verifyval(key, k)
          if k is not None:
            valprompt = self.prompts[key][2].replace('@KEY@', k)
            v = self.scr.getinput(title, valprompt, ov)
            if v is None:
              pass
            elif v or key in self.emptyok:
              # the key changed, remove the old key
              if k != ok:
                del getattr(self.conf, key)[ok]
              getattr(self.conf, key)[k] = v

  def updatecasefiles(self, key: str) -> None:
    '''
    Update :py:attr:`.conf`,``.cases`` or ``.exps`` related dir/ext changes

    Args:
      key (str): The key that triggered the update
    '''
    if key == 'casedir' or key == 'caseext':
      dir = self.get('casedir')
      ext = self.get('caseext')
      fileskey = 'cases'
    elif key == 'expdir' or key == 'expext':
      dir = self.get('expdir')
      ext = self.get('expext')
      fileskey = 'exps'
    files = [name for name in sorted(os.listdir(dir)) \
                    if os.path.splitext(name)[1] == ext]
    if not files:
      pass
    else:
      self.set(fileskey, files)

  def modifyconf(self, key: str, title: str) -> None:
    '''
    High-level method to modify :py:attr`.conf`.``key`` using menus and prompts

    Args:
      key (str): Configuration key
      title (str): Display title for prompts/menus
    '''
    if isinstance(getattr(self.conf, key), list):
      self.modifylist(key, title)
    elif isinstance(getattr(self.conf, key), dict):
      self.modifydict(key, title)
    elif key in self.dirs:
      path = self.get(key) if self.isset(key) else ''
      path = Path(path) if os.path.isdir(path) else Path.cwd()
      self += (key, self.scr.getdir(title, self.prompts[key],
                                    path=path, allownew=(key == 'phasedir')))
      if key in ('casedir', 'expdir') and self.isset(key):
        self.updatecasefiles(key)
    elif key in self.files:
      path = os.path.dirname(self.get(key)) if self.isset(key) else ''
      path = Path(path) if os.path.isdir(path) else Path.cwd()
      self += (key, self.scr.getfile(title, self.prompts[key], path,
                                      filere=self.files[key]))
    else:
      self += (key, self.scr.getinput(title,
                                      self.prompts[key],
                                      getattr(self.conf, key)))
      if key in ('caseext', 'expext'):
        self.updatecasefiles(key)
