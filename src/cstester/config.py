import yaml
from dataclasses import asdict, dataclass, field, MISSING
from typing import Any, Dict, List, Optional, Union

@dataclass
class CSTesterConfig:
  '''
  CSTesterConfig

  A dataclass which holds the actual configuration values for
  :class:`.CSTester`

  This class collects configuration options which can be saved/loaded
  '''
  #: Paths for submissions, test files, template dir
  phasedir: str = ''
  #: The submissions.zip containing group zips
  phasezip: str = ''
  #: Keyfile to help associate zips with their group number
  keyfile: str = ''
  #: A regex for properly named zips to associate with group number
  groupre_str: str = ''
  #: Regex patterns of files/dirs to exclude from submitted zips
  zipexclude_strs: List[str] = field(default_factory=lambda: [])
  #: Regex patterns of files to put in specific locations from submitted zips
  zipinclude_strs: Dict[str, str] = field(default_factory=lambda: {})
  #: Number/range list of all groups
  allgroups: str = ''
  #: Number/range list of groups to **only** include
  include: str = ''
  #: Number/range list of groups to exclude
  exclude: str = ''
  #: Regex patterns of files to match for the freeze operation
  freezefiles: List[str] = field(default_factory=lambda: [])
  #: Regex patterns of files to match for the clean operation
  cleanfiles: List[str] = field(default_factory=lambda: [])
  #: Path containing input test cases
  casedir: str = ''
  #: The file extension of input test cases
  caseext: str = ''
  #: A list of test cases found from casedir ending with caseext
  cases: List[str] = field(default_factory=lambda: [])
  #: Path containing expected output files
  #: The basenames of expected output/input test cases should match
  expdir: str = ''
  #: The file extension of expected output files
  expext: str = ''
  # A list of expected outputs found from expdir ending with expext
  exps: List[str] = field(default_factory=lambda: [])
  #: Command to test their program, shlex.split(testcmd)[0] is their program
  #: input test cases are either:
  #: passed via argument with @case@
  #: or, if @case@ is not present in testcmd, the case is piped to stdin
  testcmd: str = ''
  #: A list of commands to run, in order, from each group directory
  #: (if a command fails, later commands aren't ran)
  #: this can be used to simulate a `make` command
  prepcmds: List[str] = field(default_factory=lambda: [])
  #: A document name that should be within each submission
  #: this filename, these files can be quickly read for all groups
  readmename: str = 'writeup.txt'
  #: Regex patterns of strings to search for within files
  searchstrs: List[str] = field(default_factory=lambda: [])
  #: Regex patterns of files to search for searchstrs
  searchfiles: List[str] = field(default_factory=lambda: [])

  def to_yaml(self) -> str:
    '''
    Returns:
      str: configuration

    A YAML string which can be written to a file

    ``yaml.dump(asdict(self))``
    '''
    config = asdict(self)
    return yaml.dump(config)

  @classmethod
  def from_yaml(cls, filename: str) -> 'CSTesterConfig':
    '''
    Args:
      filename (str): Path to a YAML file

    Returns:
      CSTesterConfig: new instance
    '''
    with open(filename, 'r') as infile:
      kwargs = yaml.safe_load(infile)
    return cls(**kwargs)

  @classmethod
  def default_value(cls, field: str) -> Union[str, List[str], Dict[str, str]]:
    '''
    Args:
      field (str): CSTesterConfig attribute name

    Returns:
      Default value of attribute

    Used to reset a data field back to its default

    The parameter ``field`` must be a valid attribute, i.e.,
    ``hasattr(cls, field) == True``
    '''
    if cls.__dataclass_fields__[field].default_factory is not MISSING:
      return cls.__dataclass_fields__[field].default_factory()
    return cls.__dataclass_fields__[field].default
