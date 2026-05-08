#! /usr/bin/env python3

'''
    TestOutput - a Python script to test a program
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
  testOutput.py
  given a directory with test cases, the casedir,
    we give each test case to the program as input
  input is either piped in via stdin,
    or the input filename is given to the program where @in is an argument
  expected output is optional, and lives in expdir,
    we verify the actual output matches the expected output
  if there is no expected output, we display the input with the actual output
  if there is expected output we only do this if it differs,
    otherwise we print a message that the output matches
  we handle and give notice of any cases that ended in error/exception

    Example Makefile usage where this script is located in ../

$ tail -n7 Makefile | expand -t 2
.PHONY: test
test: obj/$(BIN) ../testOutput.py ../diffwin.py ../cursemenu.py
  python3 ./test/testOutput.py \
    --casedir test/cases --caseext .mC \
    --expdir test/exp --expdir .exp \
    --program $<
    --args arg1 key=val "multi-word arg" --input=@in
'''

import argparse, os, re, shlex, sys
from signal import Signals
from subprocess import Popen, PIPE
sys.dont_write_bytecode = True
from diffwin import DiffWindow

'''
runproc(cmd, filepos, filename)
  input:
    cmd:      list, command specified to execute
    filearg:  if filearg is none we pipe the file as stdin
    filename: the input filename
  returns:
    stdout, stderr, returncode
    stdout and stderr are strings
    returncode  = 0: normal
                = 1: error
                < 0: signal
'''
def runproc(cmd, filearg, filename):
  stdout, stderr, retcode = '', '', 1
  try:
    pipein = None
    # filearg indicates whether the input file was given as an argument
    if filearg:
      pipein = None
    else:
      with open(filename, 'r') as infile:
        pipein = infile.read()
    proc = Popen(cmd, universal_newlines=True,
                  stdin=(None if filearg else PIPE), stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate(input=pipein)
    retcode = proc.returncode
  except Exception as e:
    if stderr:
      stderr += '\n'
    stderr += f'runproc: {e}'
    retcode = 1
  return stdout, stderr, retcode

'''
dotests(cases, runstr)
  input:
    cases:   dict, key = case file, value = exp file or None
    runstr:  shlex.join([program] + args)
  executes the test for each case in cases
  displays output if possible
    (non-normal exit may suppress output)
  displays comparison if exp file exists and output doesn't match
  it no exp file displays input and output
'''
def dotests(cases, runstr):
  errortests = {}
  # if we have '@in' in the runstr we replace that with our input file
  filearg = runstr.find('@in')
  # if @in is in the runstr, that is the place for the input argument
  # if @in is not in the runstr, we pipe the input to the program via stdin
  # if we don't have @in in our runstr just set filepos to None
  if filearg < 0:
    filearg = None
    cmd = shlex.split(runstr)
  else:
    runstr = re.sub('@in', '\"@in\"', runstr)
  # for each mC file . . .
  for inFile in cases:
    # the test name is the filename without an extension
    test = os.path.splitext(os.path.basename(inFile))[0]
    if filearg:
      cmd = shlex.split(re.sub('@in', inFile, runstr))
    stdout, stderr, retcode = runproc(cmd, filearg, inFile)
    # bad return codes
    if retcode != 0:
      if stderr.strip():
        print(stderr.rstrip())
      if stdout.strip():
        print(stdout.rstrip())
      if retcode > 0:
        print(f'^^ {test} terminated with exception')
        errortests[test] = 'exception'
      else:
        print(f'^^ {test} signal {Signals(-retcode).name}')
        errortests[test] = f'signal {Signals(-retcode).name}'
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
      with DiffWindow(f'Test {test} input', 'Actual output') as win:
        win.showdiff(lhs, rhs)
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
    with DiffWindow(f'Test {test} output', 'Expected output') as win:
      win.showdiff(out, exp)
  return errortests

if __name__ == '__main__':
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
                help='Program arguments, specify input filenames with @in')

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
