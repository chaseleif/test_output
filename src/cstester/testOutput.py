#! /usr/bin/env python3

'''
  ``testoutput`` command

  Given a directory with test cases (casedir), run each case through a program
  and optionally compare output against expected files in expdir

  Input handling:
  - Piped to stdin or

  - Passed as an argument where ``@case@`` is replaced with the case filename

  Behavior:
  - If there is an expected output file,
  compare actual output to expected and display differences when they differ

  - If no expected output exists, display input and actual output
  - Report cases that end with error or exception
  - When output matches expected output report success

  Example usage with the program: ``./obj/prog``
    (program expects an input filename as argument)

  ``./obj/prog --input=@case@``
'''

import argparse, os, re, shlex, sys
from typing import Dict, List, Optional
from .diffwin import DiffWindow
from .utils import runprocess

def dotests(cases: Dict[str, Optional[str]], runstr: str) -> Dict[str, str]:
  '''
  Execute tests for each cases in ``cases`` and report results

  Args:
    cases (dict): Mapping of case_file -> expected_file or None
    runstr (str): Command string, e.g., shlex.join([program] + args)

  Returns:
    Dict[str, str]: [Error testcases, error strings]

  Runs the program for each test case, capturing output, and

  - If an expected output file exists, compares outputs and displays diff

  - If no expected output exists, displays input and output

  - Tracks non-normal exits to display following the final test case
  '''
  title = 'CSTester'
  errortests = {}
  # if we have '@case@' in the runstr we replace that with our input file
  filearg = runstr.find('@case@')
  # if @case@ is in the runstr, that is the place for the input argument
  # if @case@ is not in the runstr, we pipe the input to the program via stdin
  # if we don't have @case@ in our runstr just set filepos to None
  if filearg < 0:
    filearg = None
    cmd = shlex.split(runstr)
  else:
    runstr = re.sub('@case@', '\"@case@\"', runstr)
  # for each mC file . . .
  for inFile in cases:
    # the test name is the filename without an extension
    test = os.path.splitext(os.path.basename(inFile))[0]
    if filearg:
      cmd = shlex.split(re.sub('@case@', inFile, runstr))
    stdout, stderr, retcode = runprocess(cmd, filearg, inFile)
    # bad return codes
    if retcode != 0:
      if stderr.strip():
        print(stderr.rstrip())
      if stdout.strip():
        print(stdout.rstrip())
      errortests[test] = stderr.split('\n')[-1]
      continue
    # if output is empty then treat this as an error
    if not stdout.strip() and not stderr.strip():
      errortests[test] = 'no output'
      continue
    # no expected output file, print actual output and the input
    if cases[inFile] is None:
      # lhs will be test input
      with open(inFile, 'r') as infile:
        lhs = [line.rstrip() for line in infile.readlines()]
      # rhs will be actual output
      rhs = [line.rstrip() for line in stderr.split('\n') \
                            if line.strip() != '']
      rhs += [line.rstrip() for line in stdout.split('\n') \
                            if line.strip() != '']

      with DiffWindow() as win:
        win.scr.diffwindow((title,
                            f'Test {test} input', lhs,
                            'Actual output', rhs))
      continue
    # we have an expected output file
    out = [line.rstrip() for line in stderr.split('\n') \
                          if line.strip() != '']
    out += [line.rstrip() for line in stdout.split('\n') \
                            if line.strip() != '']
    with open(cases[inFile], 'r') as infile:
      exp = [line.rstrip() for line in infile.readlines() \
                              if line.strip() != '']
    matches = True if len(out) == len(exp) else False
    if matches:
      for lhs,rhs in zip(out, exp):
        # If they don't match
        if lhs != rhs:
          matches = False
          break
    # if matches is True then our output matched
    if matches == True:
      print(f'Test {test} output matches expected output\n')
      continue
    with DiffWindow() as win:
      win.scr.diffwindow((title,
                          f'Test {test} output', out,
                          'Expected output', exp))
  return errortests

def testoutput_main() -> None:
  '''
  Driver method for dotests

  Uses ``argparse`` to parse arguments, then runs dotests

  Args:
    casedir (str): Directory containing test case files
    caseext (str, Optional): File extension of case files
    expdir (str, Optional): Directory containing expected output
    expext (str, Optional): File extension of exp files
    program (str): Path of program to test

  The remainder of arguments are passed to the program

  - If ``@case@`` is given, it is replaced with the casefile path
  - Otherwise the casefile is read and piped to the program's ``stdin``
  '''
  parser = argparse.ArgumentParser( description=sys.argv[0] + \
                                      ' - a Python script to test a program',
                                    prog=sys.argv[0])
  parser.add_argument('--casedir', metavar='<path>', required=True,
                      help='Path containing test case files')
  parser.add_argument('--caseext', metavar='<ext>', default='',
                      help='Extension of test input files')
  parser.add_argument('--expdir', metavar='<path>', default=None,
                      help='Path containing expected output files')
  parser.add_argument('--expext', metavar='<ext>', default='',
                      help='Extension of expected outputs')
  parser.add_argument('--program', metavar='<program>', required=True,
                      help='Path to program to test')
  parser.add_argument('--args', nargs=argparse.REMAINDER,
                help='Program arguments, specify input filenames with @case@')

  args = vars(parser.parse_args())
  program = args['program']
  if not os.path.isfile(program):
    print(f'ERROR: program {program} does not exist')
    sys.exit(1)
  if not os.access(program, os.X_OK):
    print(f'ERROR: program {program} is not executable')
    sys.exit(1)

  casedir = args['casedir']
  if not os.path.isdir(casedir):
    print(f'ERROR: path {casedir} is not a directory')
    sys.exit(1)
  caseext = args['caseext']
  # list of test cases
  cases = [os.path.splitext(case)[0] \
            for case in sorted(os.listdir(casedir)) \
              if os.path.splitext(case)[1] == caseext]

  expdir = args['expdir']
  expext = args['expext']
  # list of expected output
  if expdir and os.path.isdir(expdir):
    expfiles = [os.path.splitext(exp)[0] \
        for exp in os.listdir(expdir) if os.path.splitext(exp)[1] == expext]
  else:
    expfiles = []
  # map of test case to expected output
  cases = {os.path.join(casedir, case+caseext) :
            (os.path.join(expdir, case+expext) \
              if case in expfiles else None) for case in cases}

  if len(cases) == 0:
    print(f'ERROR: no test cases found in {casedir}')
    sys.exit(1)

  cmd = args['program']
  cmd = [cmd] + args['args'] if args['args'] else [cmd]
  cmd = shlex.join(cmd)

  # Do the tests
  errortests = {}
  try:
    errortests = dotests(cases, cmd)
  except KeyboardInterrupt:
    errortests[os.path.basename(sys.argv[0])] = 'KeyboardInterrupt'
  except EOFError:
    errortests[os.path.basename(sys.argv[0])] = 'EOFError'
  if len(errortests) > 0:
    for test, result in errortests.items():
      print(f'{test} terminated with {result}')
    sys.exit(1)

if __name__ == '__main__':
  testoutput_main()
