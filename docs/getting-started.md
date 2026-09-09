# Getting started

## Install

```console
python -m pip install shell-next
```

Python 3.14 or newer is required. There are no runtime package dependencies.
Install the shell you intend to use: Bash on Linux, PowerShell 7 (`pwsh`) on
Windows, or the Windows-provided cmd interpreter.

## Run a command

Save this as `example.py` and run `python example.py`:

```python
import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main() -> None:
    backend = Backend.CMD if os.name == "nt" else Backend.BASH
    config = SessionConfig(backend=backend)
    async with use_shell_session(config) as shell:
        command = ProcessCommand(sys.executable, ("-c", "print('hello from shell-next')"))
        result = await shell.run(command, check=True, timeout=10)
        print(result.stdout.tail.decode("utf-8"), end="")


asyncio.run(main())
```

For PowerShell, select `Backend.POWERSHELL`. `SessionConfig(executable=...)`
can point to a specific interpreter. A cold PowerShell startup on a busy host
may need a larger `startup_timeout`, such as 30 seconds.

## Keep state between commands

Within an active session, use the portable helpers:

```python
await shell.chdir("/srv/project")  # Use a Windows path on Windows.
await shell.set_env("BUILD_MODE", "release")
print(await shell.get_cwd())
print(await shell.get_env("BUILD_MODE"))
await shell.unset_env("BUILD_MODE")
```

For native variables or functions, use `SessionScript`. Scripts use the selected
backend's language; shell-next does not translate shell syntax.

```python
from shell_next import SessionScript

# Bash example, inside an active Bash session:
await shell.run(SessionScript("answer=42"), check=True)
result = await shell.run(SessionScript('printf "%s" "$answer"'), check=True)
assert result.stdout.tail == b"42"
```

Continue with the [usage guide](usage.md) for interactive input and capture, or
[application testing](testing.md) to replace native execution with a mock.
