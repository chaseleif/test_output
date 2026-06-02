CSTester
========

.. BEGINDOCS

``CSTester`` is a Python curses package
to automate Computer Science programming assignment evaluation.



Configuration options
~~~~~~~~~~~~~~~~~~~~~

- phasedir

  The directory containing groups' submissions

- phasezip

  A zip containing groups' zipfiles

- keyfile

  Keys to associate with group numbers to aid extraction

- groupre_str

  A regex to extract group numbers from group zip filenames

- zipexclude_strs

  A list of regex patterns to exclude files if any portion of
  the filename matches a pattern

- zipinclude_strs

  A map of files to explicitly place at a location
  relative to the group's root directory

- allgroups

  A calculated number/range list and includes all group numbers

- include

  A number/range list of groups to **only** include

- exclude

  A number/range list of groups to exclude

- freezefiles

  A pattern for files to "freeze"

- cleanfiles

  A pattern for files to remove with the clean command

- casedir

  The directory containing input test cases

- caseext

  The file extension of input test cases

- cases

  A calculated list of input test cases

- expdir

  The directory containing expected output files

- expext

  The file extension of expected output files

- exps

  A calculated list of expected output files

- testcmd

  The testing command to run from each group's directory

- prepcmds

  A list of commands to run from selected group directories

- readmename

  The name of a text file that should be included in submissions

- searchstrs

  A list of regex patterns to search for within searchfiles

- searchfiles

  A pattern for files to include within the strings search

----

Phase directory
~~~~~~~~~~~~~~~

One of the first things wich must be done is setting up the phase directory.

The phase directory contains each group's submission in a subdirectory
in the form ``group_n``, where n is a non-negative integer.

.. note::
  Group numbers
    - Are **non-negative**, ``0|[1-9][0-9]*``
    - Do **not** have to be consecutive
    - Must **not** have leading zeroes

Extraction
~~~~~~~~~~

The extractor was made to extract ``submissions.zip``,
where each group submits a zip.

``submissions.zip`` is a zip containing other zips.

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

----

Making patches
~~~~~~~~~~~~~~

Patches can be made which can be shared
  - So that they can be applied with the ``patch`` command
  - To show changes made

To make patches, relevant files must be first frozen in their initial state.

Freezing files requires a regex to match files of interest.

All files within group directories which match the regex
  - Are duplicated in a zip archive
  - Their hash is calculated and stored in a text file

The frozen zip and hashes are stored in the root of the phase directory.
