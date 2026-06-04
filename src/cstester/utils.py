import os, re
from hashlib import md5
from signal import Signals
from subprocess import Popen, DEVNULL, PIPE
from typing import List, Optional, Tuple
from pathlib import Path

def collapsenumrange(val: str) -> Optional[str]:
  '''
  Order and collapse a number/range string into its optimal form

  Args:
    val (str): A valid string with numbers and ranges, e.g., '1,3,1,4-5'

  Returns:
    str: The collapsed number/range string, or None if val was invalid
  '''
  match = re.fullmatch(r'^(\d+|\d+-\d+)((?:,)(\d+|\d+-\d+))*$', val)
  if not match:
    return None
  nums = []
  for num in val.split(','):
    if num.isnumeric():
      nums.append(int(num))
    else:
      start, stop = num.split('-')
      start, stop = int(start), int(stop)
      if start > stop:
        return None
      nums.extend([num for num in range(start,stop+1)])
  nums = sorted(list(set(nums)))
  val = []
  first = prev = nums[0]
  for num in nums[1:]:
    if num == prev+1:
      prev = num
    else:
      if first == prev:
        val.append(f'{first}')
      else:
        val.append(f'{first}-{prev}')
      first = prev = num
  if first == prev:
    val.append(f'{first}')
  else:
    val.append(f'{first}-{prev}')
  return ','.join(val)

def expandnumrange(val: str) -> List[str]:
  '''
  Expand a number/range string into a list of numbers as strings

  Args:
    val (str): A valid number/range string, e.g., '1,3-5'

  Returns:
    List[str]: Expanded list of numbers as strings
  '''
  nums = []
  if not val:
    return nums
  for num in val.split(','):
    if num.isnumeric():
      nums.append(int(num))
    else:
      start, stop = num.split('-')
      start, stop = int(start), int(stop)
      nums.extend([num for num in range(start,stop+1)])
  return [str(num) for num in sorted(list(set(nums)))]

def getfilehash(filename: str) -> str:
  '''
  Compute and return a hash for a file

  Args:
    filename (str): Path to the file

  Returns:
    str: Hash string of the file contents
  '''
  m = md5()
  with open(filename, 'rb') as infile:
    while True:
      chunk = infile.read(4096)
      if not chunk:
        break
      m.update(chunk)
  return m.hexdigest()

def getgroups(phasedir: str) -> List[int]:
    '''
    Get the (int, sorted) valid group directories within the phase directory

    Args:
      phasedir (str): The phase directory

    Returns:
      List[str]: List of group directories within phasedir
    '''
    if not os.path.isdir(phasedir):
      return []
    groups = [name for name in os.listdir(phasedir) if \
              os.path.isdir(os.path.join(phasedir, name)) and \
              name.startswith('group_')]
    groups = sorted([int(group.split('_')[-1])for group in groups if \
                    group.split('_')[-1].isnumeric()])
    return groups

def removecommonprefix(left: str, right: str) -> Tuple[str, str]:
  '''
  This method is used to  the common prefix from 2 files

  Args:
    left (str): A path as a string
    right (str): A path as a string

  Returns:
    left and right stripped of their common prefix

  If left and right were the same then
  the returnvalue will be the basename of each prefixed with 'a/' and 'b/'
  '''
  left = Path(os.path.abspath(left)).parts
  right = Path(os.path.abspath(right)).parts
  sameindex = 0
  while sameindex < len(left) and sameindex < len(right) and \
        left[sameindex] == right[sameindex]:
    sameindex += 1
  # sameindex should always be greater than zero given left/right share root
  sameindex = max(0, sameindex-1)
  left = left[sameindex:]
  right = right[sameindex:]
  # the same file . . .
  if left == right:
    return f'a/{left[-1]}', f'b/{right[-1]}'
  return os.path.join(*left), os.path.join(*right)

def runprocess(cmd: List[str],
              filename: Optional[str]='',
              getout: Optional[bool]=True,
              geterr: Optional[bool]=True) -> Tuple[str, str, int]:
  '''
  Instantiate an instance of :py:class:`subprocess.Popen`,
  use :py:meth:`subprocess.Popen.communicate` with an optional input,
  and return its stdout, stderr and return code

  Args:
   cmd (List[str]): Command to execute (e.g., from shlex.split)
   filename (str, Optional): Path to a file to pipe to the process' stdin
   getout (bool, Optional): If True, capture and return stdout
   geterr (bool, Optional): If True, capture and return stderr

  Returns:
    Tuple[str, str, int]: (stdout, stderr, return_code)

  stdout: Text written to stdout (may be empty)

  stderr: Text written to stderr (may be empty)

  return_code: Process exit code (0 normal, > 0 error, < 0 signal)
  '''
  stdout, stderr, retcode = '', '', 1
  try:
    pipein = None
    input = None
    if filename:
      with open(filename, 'r') as infile:
        pipein = PIPE
        input = infile.read()
    proc = Popen(cmd, universal_newlines=True,
                  stdin=pipein,
                  stdout=(PIPE if getout else DEVNULL),
                  stderr=(PIPE if geterr else DEVNULL))
    stdout, stderr = proc.communicate(input=input)
    retcode = proc.returncode
  except Exception as e:
    if geterr and stderr:
      stderr += '\n'
    stderr += f'runproc: {e} '
    retcode = 1
  if retcode < 0:
    stderr += f'signal {Signals(-retcode).name}'
  elif retcode > 0:
    stderr += '(terminated with exception)'
  return stdout, stderr, retcode
