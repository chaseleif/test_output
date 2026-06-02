CSTester
========

.. BEGINDOCS

``CSTester`` is a Python curses package
to automate Computer Science programming assignment evaluation.

----

Requirements
~~~~~~~~~~~~

This project requires ``PyYAML`` and ``Python`` >= 3.9.

This is an ``ncurses`` application which provides a ``TUI``,
so a terminal with ``ncurses`` is also required.

----

Installation
~~~~~~~~~~~~

This package is available on PyPi,
and can be installed with the command ``pip install cstester``,
alternatively, you may clone the repo and ``pip install -e .``
for a "live" version.

----

Commands
~~~~~~~~

Following a ``pip install``, you are provided with 3 commands:
  1) ``cstester`` -- the main ``CSTester`` application
  2) ``diffwin`` -- a standalone driver for the ``DiffWindow`` class
  3) ``testOutput`` -- a standalone driver to test an individual program

----

Terminology
~~~~~~~~~~~

This utility was made to test many programming project/assignment submissions.

While individual submissions do not need to be "group" submissions,
this is how a submission is referred to, as a group's submission.

Group's are differentiated from each other based on their number.

.. note::
  Group numbers
    - Are **non-negative**, ``0|[1-9][0-9]*``
    - Do **not** have to be consecutive
    - Must **not** have leading zeroes

Numeric groups eases sorting and building include/exclude number/range lists
  - Commands performed need not apply to all groups
  - The "include" number/range list specifies groups to **only** include
  - The "exclude" number/range list specified groups to **not** include


A number/range list is a string with comma-separated values, each either
  - a single number
  - a range from start-stop, where start is not greater than stop

Some valid example number/range lists:
  - ``4,6,1,5,7-9`` is equivalent to ``1,4-9``
  - ``23`` a single number
  - ``0-10`` a single range for the beginning groups, including ``10``

Regular expressions
-------------------

Several options use regular expressions,
these are case-insensitive and,
*except for the search strings method*,
are used with ``re.match`` so begin with an implied caret ``^``.

Expressions are compiled with Python's re module,
so refer to their excellent documentation for additonal information.

The **group regex** string,
to extract the group number from their zip filename,
**must** have the group number in a capture group, e.g.,
``projectgroup(\d+)_.*``.

The optional **keyfile**, used to aid extraction,
is an alternative to using a group regex, but is not as efficient.

----

Input validation
~~~~~~~~~~~~~~~~

Where possible, input for options is validated.

There are 3 validations performed:
  - regex -- regexes are passed to ``re.compile`` to determine validity
  - numrange -- a valid number/range list is converted to its condensed form
  - command -- we check whether argv[0] is a shell built-in or executable file

Of these, we can't reliably verify a command
if it is not found in ``PATH`` or an executable file.

We don't want to attempt to execute the command to determine whether
the command works, as attempting to run the command may have side-effects.

.. attention::
  Command verification may be on the chopping-block

For the time being, if a command is given and fails verification
  1) substitute with a known good command, e.g., ``echo "hallo"``
  2) save your configuration
  3) replace the command in the yaml file
  4) load the configuration

----

CSTester usage
~~~~~~~~~~~~~~

The main application is invoked with the ``cstester`` command,
optionally providing a saved configuration ``.yaml`` as an argument, e.g.,
``cstester assgn1.yaml``.

In most screens
  - "cancel keys" are { <escape>, Q, q }
  - "return keys" are { <enter> }
  - "help keys" are { ?, H, h }

Some screens return immediately on a keypress, e.g.,
a prompt asking ``Y/n``, ``y/N``, or to press the ``any`` key.

When a "*yes or no*" prompt is given, the default response is capitalized.
Unless you give the lowercased response,
*case-insensitive*,
the default response is chosen.

----

The main menu
-------------

The main menu is divided into
  - phase directory setup
  - group options
  - evaluation
  - edit/view configuration
  - save configuration
  - load configuration

Configuration options can be set via the menu,
saved to a settings yaml, and then reused or modified for subsequent uses.
The settings yaml may be manually edited,
but using the menus ensures the file is correct.

----

Phase directory setup
---------------------

One of the first things wich must be done is setting up the phase directory.
This directory can be created in the extraction process,
*extraction to an existing directory removes its contents*.

The phase directory contains each group's submission in a subdirectory
in the form ``group_n``, where n is a non-negative integer.

A ``phase zip`` can be chosen to extract to the selected ``phase directory``.

The extraction keyfile and group regex
are used to associate group submission filenames with their group number.

``zip include`` is a dictionary option which specifies filenames that we
explicitly want in a specific location in the group directory,
e.g., ``"README":""`` means to put ``README`` in the group's root directory.

``zip exclude`` is a list of files and directories to **not** extract.

Both zip include and exclude are patterns compiled and used with ``re.match``.

----

Group options
-------------

This menu allows to enter number/range list strings for both
groups to **only** include as well as groups to exclude,
there are also menu entries to allow ``selection``,
which uses a curses window to select entries.

Also (currently) in the group options menu,
are the options to ``freeze`` and ``clean`` files.

Freezing files
--------------

Files to freeze are those which match an entered regex pattern.

The "freeze" operation performs 2 important functions
  - matching files are archived in a zip in the root phase directory
  - the files' hashes are stored in a text file in the root phase directory


The purpose of freezing files is to later make a patch.

If a submission requires modification to compile, or some other reason,
a patch can be made to provide the group so that they can either

  - Use the ``patch`` command to apply the patch to their file
  - Review the changes made to their submission

Making patches
--------------

Unlike with the "freeze" operation, this doesn't require a regex:
  1) the "frozen" text file is read,
  2) the hashes for files listed are compared with their stored hash
  3) when hashes differ a patch is created and placed next to the original
  4) a listing of patches made is shown (or that no files were modified)

Clean files
-----------

This operation is meant to simulate a ``make clean`` command.

Files matching a pattern withing the clean files regexes will be removed.

.. caution::

  Search for files begins at the root of each group's directory,
  so no files outside of their directory will be removed,
  but a bad pattern, e.g., a blank string ``""`` which matches anything,
  could clear the group directories.

----

Evaluation
----------

The evaluation menu provides additional simulated ``make`` commands.

The ``test`` command is the command that will run from the group's directory.
If an input test case is to be given as a command-line argument,
use ``@case@`` which will later be substituted with the case's file path.
If ``@case@`` is not present in the command-line arguments,
then the input casefile is read and passed to the program as its ``stdin``.

Preparation commands are a list of commands
which will run in each group's directory.

Commands will stop running after the first failure,
and a list of failures by-group will be displayed after completion.

Preparation commands *are not* validated commands, for obvious reasons.

Preparation commands can be used to simulate ``make clean && make``,
or for some other purpose.

There is also a ``clean`` option in this menu,
the duplicate path to clean
should be removed from either the group menu or this menu.

Search strings allows to search files matching a pattern for strings.

This can be useful for multiple reasons,
but probably the most useful is to search for potentially malicious code.

Read readmes, if each submission should have a text file,
will display the readme of each submission (or a note that it is missing).

----

Configuration options
~~~~~~~~~~~~~~~~~~~~~

See the API documentation for the ``CSTesterConfig`` dataclass
for a listing of the configuration options saved/loaded from yaml,
and a description of their use.

----

Extraction
~~~~~~~~~~

The extractor was made to extract a single zip, e.g., ``submissions.zip``,
that contains a zip for each group's submission.

Group numbers are obtained through a group regex,
or, optionally, using a keyfile.

The group regex extracts a number from a filename,
using ``re.match``, e.g.,

.. code::

  ^group_(0|[1-9][0-9]*).*\.zip$

The key-value pairs taken from the keyfile are of the form

.. code::

  ^(0|[1-9][0-9]*)(?:,.*):([^:]+)$

That is, lines start with a valid group number,
optionally followed by a comma and some series of text before a trailing colon,
finally, the key to search for in the filename is after the final colon.

For example, with

.. code::

  42,Group leader: A name, Members: Another name:groupname

if **groupname** exists within the filename
then the group number will be inferred to be **42**.

All regex matches performed during extraction are all **case-insensitive**.
*Regexes* in a keyfile **must be unique**, *group numbers* **need not be**.

Group directories are of the form ``group_n``, where ``n`` is the group number

Within the phase directory, an extraction log is created: ``phasedir/x.log``

The extraction log records general information about extraction
  - If a keyfile was used and how many keys were obtained from the keyfile
  - If files were skipped/ignored
  - If a group number was inferred from keyfile and why
  - If a group number was manually entered
    (decisions in subsequent extractions *of the same zipfile* can be repeated)
  - Which file was chosen among multiple submissions
  - How many group->file pairs were found
  - If duplicate files were ignored
  - If a submission zip had symlink files
  - If extraction of a submission zip had an exception
  - If a submission wasn't extracted due to a suspicious compression ratio
  - If duplicate files were ignored
  - If extracted files needed to be renamed

Within group directories, e.g., ``phasedir/group_1/``
  - ``group1.zip``--contains the original zipfile
  - ``sub.nfo``--contains details of the original zipfile
    The original zip filename
    The compressed size, extracted size, and compression ratio
    Whether symlink files existed (and were skipped)
    List of extracted files
    List of files excluded

**Extracting individual zip files**

The submissions zip is extracted to a temporary directory.

We examine the zip memberlist against exclude patterns,
and do not extract files which match (case-insensitive)
an exclude pattern.

For files we want at a specific location,
these can be specified in the include pattern map:

  - The ``key`` is a regex to match the file
  - The ``val`` is a relative location from the group directory

.. hint::
  include={'Makefile','','driver\.c','src}
  Will put Makefile in the group's root directory and driver.c in src/


We
exclude (and print a warning) any symlinks within the archive. We
extract the contents of the zip to a new temporary directory. We ensure
all files are chmod 600 (**owner rw**), and all directories are chmod
700 (**owner rwx**).

We move all files to the final extraction directory,
we remove any special characters from file/directory names,
and spaces are converted to underscores.
We put the original zip in the group’s directory.
A text file, ``./sub.nfo``,
will contain the zip filename,
original content list with sizes (compressed/decompressed),
and compression ratio of extracted files.

