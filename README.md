### A collection of 2 main scripts and 1 utility script to test programs

___

# TestOutput

### a Python script to test a program

*Can be used without other scripts in this repo*  
___

## Argparse generated output options

  -h, --help           Show this help message.  
  --testpath <path>    Path containing test input files  
  --testext <ext>      Extension of test input files  
  --exppath <path>     Path containing expected output files  
  --expext <ext>       Extension of expected outputs  
  --program <program>  Path to program to test  
  --args ...           Program arguments, specify input filenames with @in  

## Required arguments

- testpath: Path containing files which will be used as input to the program  
- program: Path to the program to test  

## Optional arguments

- testext: File extension for input files, if not provided use all files  
- exppath: Path containing files with expected output of the program  
(if not provided then program output is displayed)  
- expext: File extension for expected output files, used as testext  
- args: Arguments to use when running the program  
(input filename will be insert into argument @in, if specified)  
(if no @in argument exists, input file will be piped to stdin)  

___

## Output shown

Output shown will indicate whether output matched expected output  
If they do not match, a diff will be shown using either DiffWin or difflib  

___
___

# DiffWindow

### a Python curses script to compare 2 text files

*Depends on CurseMenu script in this repo*  

- Contents of files shown in 2 resizable (vertical) panes  
- Left and right panes can be unlocked and scrolled independently  
- Matching lines highlighted by default  

___

## Standalone usage

To open using the menu-driven interface: `$ python3 diffwin.py`  
To open in the diff view: `$ python3 diffwin.py file1 file2`  

___

## Example script usage

```
from diffwin import DiffWindow
if __name__ == '__main__':
  if len(sys.argv) == 3:
    lhs, rhs = [], []
    with open(sys.argv[1]) as infile: lhs = infile.readlines()
    with open(sys.argv[2]) as infile: rhs = infile.readlines()
    with DiffWindow() as win: win.showdiff(lhs, rhs)
  else:
    with DiffWindow() as win: win.mainmenu()
```

___
## Main menu

Select the left-hand side file  
Select the right-hand side file  
Show the diff between the files  
Show available commands for diff view  
Quit  

___
___

# CurseMenu

### A Python script providing supporting curses functions to draw menus

___

## Functions provided

- showmenu: draws a menu display, handles choice selection tracking and return  
- filemenu: a file selection menu to select a text file  
- drawsplitpane: draws the contents of 2 lists with a vertical screen split  

