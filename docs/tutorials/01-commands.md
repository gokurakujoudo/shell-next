# Ordinary and multiple commands

Start with a normal executable, then add literal arguments, then an ordered
sequence. This chapter works on Bash, PowerShell, and cmd.

1. Run the selected Python interpreter with `--version`. `await shell.run()`
   waits through capture and cleanup before returning the result.
2. Pass each argument separately in `ProcessCommand.args`. The spaces, ampersand,
   and pipe in the second example are data, so the shell does not execute them.
3. Await commands in a loop. `check=True` stops the sequence by raising on the
   first unsuccessful command; the three successful results remain in order.

`ProcessCommand` is for external executables. Shell built-ins such as `cd`,
PowerShell cmdlets, redirection, and pipes require the portable state helpers or
`SessionScript`, covered in later chapters. Replace `sys.executable` with an
installed executable such as `git` when adapting this example.

## Full example

File: [`examples/01-commands.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/01-commands.py).

```console
python examples/01-commands.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 01-commands.py -->
```python
"""Run one command, preserve arguments, then run an ordered sequence."""

import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    config = SessionConfig(backend=backend, startup_timeout=30)
    async with use_shell_session(config) as shell:
        # 1. Run an ordinary external command through the selected shell.
        result = await shell.run(ProcessCommand(sys.executable, ("--version",)), check=True)
        assert "Python 3." in result.stdout_str()
        print(result.stdout_str(), end="")

        # 2. Arguments remain literal, including spaces and shell operators.
        value = "two words & literal | text"
        command = ProcessCommand(sys.executable, ("-c", "import sys; print(sys.argv[1])", value))
        result = await shell.run(command, check=True)
        assert result.stdout_str().strip() == value
        assert result.command is command

        # 3. Await each command to preserve order and stop on the first failure.
        outputs = []
        for number in (1, 2, 3):
            command = ProcessCommand(sys.executable, ("-c", f"print({number})"))
            result = await shell.run(command, check=True, timeout=10)
            outputs.append(result.stdout_str().strip())
        assert outputs == ["1", "2", "3"]
        print(outputs)


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
