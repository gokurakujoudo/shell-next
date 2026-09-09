# Troubleshooting

## The interpreter does not start

Check the selected backend and executable. Bash requires Linux/POSIX support;
the PowerShell and cmd adapters require Windows. PowerShell 7 uses `pwsh`, not
Windows PowerShell 5.1's `powershell.exe`. Set `executable` to an explicit path
when it is absent from PATH. Increase `startup_timeout` for a cold or busy host.

## A second command is rejected

The default policy is `ConcurrencyPolicy.REJECT`. Finish the current command
or use `ConcurrencyPolicy.QUEUE` for FIFO execution. Calling another command
from the owner of a scoped command raises `SessionReentrancyError`, preventing
the owner from waiting on its own lease. Use another session for independent work.

## A prompt never arrives

Programs may buffer output when they are not connected to a terminal. Configure
the program to flush prompts; for Python children, `-u` enables unbuffered output.
Match literal bytes and select the correct stdout/stderr stream. The prompt must
fit `CaptureConfig.match_bytes`. Terminal and PowerShell Host prompts are not
standard stream prompts and are unsupported.

## The command is still running after a wait timed out

`handle.wait(wait_timeout=...)` only limits the observation. Use an execution
deadline, call `handle.stop()`, or use the managed `run()`/`command()` ownership
interfaces when the operation must stop with its owner.

## Output is marked incomplete

Inspect `end`, `sealed`, `received`, `committed`, and `unread_possible` on each
stream result. A bounded memory tail may truncate output; file capture may fail;
forced cleanup or an output drain deadline may leave unread bytes. Choose an
existing writable capture directory when full retention is required.

## A session is broken after stopping a command

This is expected after forced interruption. Create a new session explicitly.
Automatic restart would silently lose cwd, environment, variables, and functions.

## Sudo fails or cleanup is uncertain

Use an asynchronous password provider returning bytes for interactive sudo.
Business stdin is not the password channel. Noninteractive mode requires
credentials or sudo policy that permits execution without a prompt. Privileged
descendants cannot be guaranteed contained after changing identity, so
`strict_cleanup=True` is rejected before execution.

## Reporting a problem

Include the package/Python version, OS, backend, a minimal reproduction, and
sanitized result fields. Remove passwords, tokens, and sensitive command output.
[Open an issue](https://github.com/gokurakujoudo/shell-next/issues).
