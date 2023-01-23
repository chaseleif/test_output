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
    Example Makefile usage given a top-level directory and ./assgnX/ subfolders
    ( with the scripts in the top level-dir and Makefile in assgn dir )
    This example usage (and below import) includes the DiffWindow script

$ tail -n14 Makefile
test/cursemenu.py: ../cursemenu.py
	cp $< $@

test/diffwin.py: ../diffwin.py test/cursemenu.py
	cp $< $@

test/testOutput.py: ../testOutput.py
	cp $< $@

test: obj/$(BIN) test/diffwin.py test/testOutput.py
	python3 ./test/testOutput.py \
--testpath test/cases --testext .mC \
--exppath test/exp --expext .exp \
--program $<
'''

import argparse, difflib, os, sys
from signal import Signals
from subprocess import Popen, PIPE
sys.dont_write_bytecode = True
try:
  from diffwin import DiffWindow
except ModuleNotFoundError: DiffWindow = None
sys.dont_write_bytecode = False

'''
runproc(cmd, filepos, filename)
  input:
    cmdv:     list, command specified to execute
    filepos:  None if we need to set stdin to be a file
    filename: the string filename
  returns:
    a list: [output, returncode]
    output is a list: [stdout, stderr]
    stdout or stderr are strings and may be empty
    returncode is a numeric value indicating exit code
                = 0: normal exit
                = 1: uncaught exception
                < 0: exception with negative signal number
'''
def runproc(cmd, filepos = None, filename=''):
  # the output of a failed run
  output = ['', '']
  try:
    # our input text
    intext = None
    # filepos is the position of runstr for the input file to use
    if not filepos:
      # open the input file and pass it as stdin to Popen
      with open(filename, 'r') as infile:
        intext = infile.read()
    proc = Popen(cmd, stdin = PIPE, stdout = PIPE, stderr = PIPE,
                  shell = True, universal_newlines = True)
    output = proc.communicate(input = intext)
    return output, proc.returncode
  except Exception as e:
    print('ERROR (' + sys.argv[0] + ':runproc): ' + str(e))
    return output, 1

'''
dotests(cases, program, runstr)
  input:
    cases:   dict, key = case file, value = exp file or None
    program: the program to test
    runstr:  program + args
  executes the test for each case in cases
  displays actual output (if possible)
    segmentation faults may suppress output
  displays comparison with expected output (if exp file exists)
    otherwise displays the input file
'''
def dotests(cases, program, runstr):
  # if we have '@in' in the runstr we replace that with our input file
  filepos = runstr.find('@in')
  # otherwise cmd is just our runstr
  cmd = runstr
  output = None
  confirm = 'n'
  # if we don't have @in in our runstr just set filepos to None
  if filepos < 0:
    filepos = None
  # for each mC file . . .
  for inFile in cases:
    # the test name is the filename without an extension
    test = inFile.split('.')[0].split('/')[-1]
    print('~~~~~\n~~ Test ' + test + ':')
    if filepos:
      cmd = runstr[:filepos] + inFile + runstr[filepos+3:]
    output = runproc(cmd, filepos, inFile)
    # handle bad return codes
    if output[1] != 0:
      print('~~ cmd:', cmd + '\n')
      if len(output[0][0]) > 0 and output[0][0].rstrip() != '':
        print('~~ stdout:')
        print(output[0][0].rstrip() + '\n')
      if len(output[0][1]) > 0 and output[0][1].rstrip() != '':
        print('~~ stderr:')
        print(output[0][1].rstrip() + '\n')
      if output[1] > 0:
        print('~~', program, 'terminated with exception')
      else:
        print('~~', program, 'terminated with signal', Signals(-output[1]))
      continue
    # handle normal exit
    # we have a corresponding file for expected output
    if cases[inFile]:
      out = [line.rstrip() for line in output[0][0].split('\n') \
                              if line.strip() != '']
      exp = []
      with open(cases[inFile], 'r') as infile:
        exp = [line.rstrip() for line in infile.readlines() \
                                if line.strip() != '\n']
      matches = True if len(out) == len(exp) else False
      if matches:
        for i, line in enumerate(exp):
          # If they don't match
          if line != out[i]:
            matches = False
            break
      # if matches is True then our output matched
      if matches == True:
        print('Actual output matches expected output\n')
      else:
        # ask whether to use curses or difflib
        if DiffWindow:
          confirm = input('Open ' + test + ' in curses? (y/n): ')
        if confirm == 'y':
          with DiffWindow() as win: win.showdiff(out, exp)
        else:
          for line in difflib.context_diff(a=out, fromfile='actual',
                                            b=exp, tofile='expect'):
            print(line)
    # no corresponding output, print our output and the input
    else:
      # ask whether to use curses
      if DiffWindow:
        confirm = input('Open ' + test + ' in curses? (y/n): ')
      if confirm != 'y': confirm = None
      # lhs will be all test output
      lhs = [] if confirm else None
      if len(output[0][1]) > 0 and output[0][1].rstrip() != '':
        if confirm:
          lhs.append('~~ stderr:')
          lhs += [line.rstrip() for line in output[0][1].split('\n') \
                                            if line.strip() != '']
        else:
          print('~~ stderr:')
          print(output[0][1].strip()+'\n')
      if len(output[0][0]) > 0 and output[0][0].rstrip() != '':
        if confirm:
          lhs.append('~~ stdout:')
          lhs += [line.rstrip() for line in output[0][0].split('\n') \
                                            if line.strip() != '']
        else:
          print('~~ stdout:')
          print(output[0][0].rstrip()+'\n')
      # rhs will be test input
      rhs = [] if confirm else None
      if confirm:
        rhs.append('~~ input (' + test + '):')
      else:
        print('~~ input (' + test + '):')
      # the input file
      with open(inFile, 'r') as infile:
        if confirm: rhs += [line.rstrip() for line in infile.readlines() \
                                                        if line.strip() != '']
        else: print(infile.read()+'\n')
      if confirm:
        with DiffWindow() as win: win.showdiff(lhs, rhs)

if __name__ == '__main__':
  parser = argparse.ArgumentParser(add_help=False,
                                    description=sys.argv[0] + \
                                      ' - a Python script to test a program',
                                    argument_default=argparse.SUPPRESS,
                                    prog=sys.argv[0],
                                    epilog='Required: testpath, program')
  parser.add_argument('-h', '--help', action='store_true',
                      help='Show this help message.')
  parser.add_argument('--testpath', metavar='<path>',
                      help='Path containing test input files')
  parser.add_argument('--testext', metavar='<ext>', default='',
                      help='Extension of test input files')
  parser.add_argument('--exppath', metavar='<path>',
                      help='Path containing expected output files')
  parser.add_argument('--expext', metavar='<ext>', default='',
                      help='Extension of expected outputs')
  parser.add_argument('--program', metavar='<program>',
                      help='Path to program to test')
  parser.add_argument('--args', nargs=argparse.REMAINDER,
                help='Program arguments, specify input filenames with @in')

  args = vars(parser.parse_args())
  if 'help' in args or 'testpath' not in args or 'program' not in args:
    parser.print_help()
    sys.exit(0)

  # Collect the input files in a dictionary
  # key = inFile, value = (expFile or None)
  cases = {}
  if args['testpath'][-1] != '/': args['testpath'] += '/'
  if 'exppath' in args and args['exppath'][-1] != '/': args['exppath'] += '/'
  for inFile in os.listdir(args['testpath']):
    if not inFile.endswith(args['testext']): continue
    # this is where the expected output file would be
    expFile = None
    if 'exppath' in args:
      expFile = args['exppath'] + inFile.split('.')[0] + args['expext']
      if not os.path.isfile(expFile): expFile = None
    # set the full path to the input file to equal expected output file
    cases[args['testpath'] + inFile] = expFile

  cmd = args['program']
  if 'args' in args: cmd += ' ' + ' '.join(args['args'])
  # Do the tests
  try:
    dotests(cases, args['program'], cmd)
  # Allow ctrl-c to exit
  except KeyboardInterrupt: pass
  # Allow ctrl-d to exit
  except EOFError: print('< EOF')

# vim: tabstop=2 shiftwidth=2 expandtab
