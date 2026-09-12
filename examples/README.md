# Runnable examples

Start with the [step-by-step tutorial](../docs/tutorials/index.md), which owns the
ordered chapter list, instructions, and the exact code shown in these files.

From the checkout root, run `python examples/01-commands.py bash` on Linux, or
replace `bash` with `powershell` or `cmd` on Windows. Python 3.14+ and shell-next
must be installed. Files are standalone; the tutorial covers each file's
arguments and prerequisites. Sudo requires an explicit mode and an authorized
Linux account. Mock examples never start native programs.

Native examples use temporary workspaces where files are needed and close their
sessions before cleanup. They do not retain demonstration files on completion.
Documentation tests verify that published Python and these files remain identical;
platform integration tests execute the exact published source.
