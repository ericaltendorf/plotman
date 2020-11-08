# plotman
Chia plotting manager

This is a tool for managing [Chia](https://github.com/Chia-Network/chia-blockchain)
plotting operations.  The tool provides several classes of functionality, which can
be used together or independently:

1. Automatic spawning of new plotting jobs, possibly overlapping ("staggered") on
one or multiple temp directories, rate-limited globally and by per-temp-dir limits.

1. Management of ongoing plotting jobs, both monitoring (view progress, resources
used, temp files, etc.) and control (suspend, resume, plus kill and clean up
temp files).  Management works by inspecting process tables, open files, and
logfiles of the jobs, and works for any plotting jobs with STDOUT/STDERR redirected
to a file in a known logfile directory (in particular, management will work for
jobs started outside of the plotman tool).

1. Analyzing performance statistics of past jobs, to aggregate on various plotting
parameters or temp dir type.  (Code mostly written but not integrated into this
repo yet.)

The tool is interactive, with its own mini CLI, and a background thread for
spawning new plotting jobs.  Future work could make it usable either interactively
or as a true command line tool.

The tool relies on reading the chia plot command line arguments and the format of
the plot tool output.  Changes in those may break this tool.

Code dependencies include

1. texttable for generating pretty tables
1. psutil for inspecting process and system info

