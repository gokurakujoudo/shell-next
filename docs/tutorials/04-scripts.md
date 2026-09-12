# Native scripts and script files

Use `SessionScript` when shell syntax is the task. Choose the backend entry;
the library never translates script languages.

1. Run a pipeline that selects `apple`. Bash uses `printf` and `grep`, PowerShell
   uses `Where-Object`, and cmd uses `findstr`. These are native tools/operators,
   not portable `ProcessCommand` arguments.
2. Assign a native variable in one call and read it in another. The interpreter
   stays alive, so the value survives. Bash and PowerShell also preserve native
   functions and aliases; cmd has no equivalent function/alias capability.
3. Write a complete trusted `.sh`, `.ps1`, or `.cmd` file in the temporary
   workspace, read its exact source, and execute it in the existing session.

The third example runs **file contents**, not a separate script interpreter:
file-relative variables such as PowerShell `$PSScriptRoot`, Bash `$0`, and cmd
`%~dp0` do not identify the original file. For an independent script process,
use `ProcessCommand('bash', ('path/to/script.sh',))` on Linux or
`ProcessCommand('pwsh', ('-NoProfile', '-File', 'path/to/script.ps1'))` on Windows.
For a cmd batch file use native `call` syntax in `SessionScript`, with a trusted,
properly quoted path. Child-process state changes do not update the parent shell.

Scripts are trusted code, not a sandbox. Their state changes are not rolled back
on failure. Do not use the reserved `sn_` namespace, Bash descriptor 9, or terminate
the persistent interpreter with `exit`. Keep caller data in structural arguments.

## Full example

File: [`examples/04-scripts.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/04-scripts.py).

```console
python examples/04-scripts.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 04-scripts.py -->
```python
"""Run native syntax, preserve shell variables, and execute a trusted script file."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import Backend, SessionConfig, SessionScript, use_shell_session


async def main(backend: Backend) -> None:
    # The three entries are native programs with the same observable intent.
    assign, read, pipeline, suffix = {
        Backend.BASH: (
            "demo_answer=42",
            'printf "%s\\n" "$demo_answer"',
            "printf 'apple\\npear\\n' | grep apple",
            ".sh",
        ),
        Backend.POWERSHELL: (
            "$demo_answer = 42",
            "Write-Output $demo_answer",
            "'apple', 'pear' | Where-Object { $_ -eq 'apple' }",
            ".ps1",
        ),
        Backend.CMD: (
            'set "demo_answer=42"',
            "echo %demo_answer%",
            "(echo apple&echo pear) | findstr apple",
            ".cmd",
        ),
    }[backend]
    with TemporaryDirectory(prefix="shell-next-script-") as directory:
        config = SessionConfig(backend=backend, cwd=directory, startup_timeout=30)
        async with use_shell_session(config) as shell:
            # 1. Operators and shell built-ins belong in SessionScript.
            result = await shell.run(SessionScript(pipeline), check=True)
            assert result.stdout_str().strip() == "apple"

            # 2. A variable assigned in one call survives into the next call.
            await shell.run(SessionScript(assign), check=True)
            result = await shell.run(SessionScript(read), check=True)
            assert result.stdout_str().strip() == "42"

            # 3. Load a trusted file as native source in the existing session.
            path = Path(directory) / ("demo" + suffix)
            path.write_text(assign + "\n" + read + "\n", encoding="utf-8")
            result = await shell.run(SessionScript(path.read_text(encoding="utf-8")), check=True)
            assert result.stdout_str().strip() == "42"
            print(result.stdout_str(), end="")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
