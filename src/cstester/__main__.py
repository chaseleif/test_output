import os, sys
from .tester import CSTester
from .diffwin import DiffWindow
from .testOutput import testoutput_main

def main() -> None:
  with CSTester(sys.argv) as tester:
    tester.mainmenu()

def diff() -> None:
  with DiffWindow(sys.argv) as diff:
    if diff.scr is not None:
      diff.mainmenu()

def testoutput() -> None:
  testoutput_main()
