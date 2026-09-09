# Getting started

Install Python 3.14+ and the selected shell, then install shell-next:

```console
python -m pip install shell-next
```

This example chooses cmd on Windows and Bash on Linux:

```python
import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main() -> None:
    backend = Backend.CMD if os.name == "nt" else Backend.BASH
    async with use_shell_session(SessionConfig(backend)) as shell:
        result = await shell.run(
            ProcessCommand(sys.executable, ("-c", "print('hello')")),
            check=True,
            timeout=10,
        )
        print(result.stdout.tail.decode("utf-8"), end="")


asyncio.run(main())
```

Choose `Backend.POWERSHELL` for PowerShell 7. Set `executable` if the interpreter
is not on PATH. Use `ProcessCommand` for literal arguments and `SessionScript`
for backend-native code with persistent shell state.

Continue with the [full getting-started guide](https://gokurakujoudo.github.io/shell-next/getting-started/).
