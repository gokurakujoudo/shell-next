# Directory navigation

A shell session owns its working directory independently of the Python process.
These two examples work unchanged on all three backends.

1. Create an isolated workspace and select it with `SessionConfig.cwd`. Query
   `get_cwd()` to observe the interpreter, then inspect the cached `snapshot()`.
2. Use `chdir()` with a relative path containing spaces. The next external
   process inherits that directory. Navigate back using `..` and verify that
   Python never moved. Absolute paths also work; the final workflow uses one.

The shell closes before `TemporaryDirectory` removes its workspace, which matters
on Windows where an active process can hold a directory open. After a native
script changes directories, call `get_cwd()` before relying on the cached snapshot.

## Full example

File: [`examples/02-navigation.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/02-navigation.py).

```console
python examples/02-navigation.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 02-navigation.py -->
```python
"""Inspect and change the shell directory without changing Python's directory."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    parent_cwd = Path.cwd()
    with TemporaryDirectory(prefix="shell-next-navigation-") as directory:
        root = await asyncio.to_thread(Path(directory).resolve)
        child = root / "project with spaces"
        child.mkdir()
        config = SessionConfig(backend=backend, cwd=str(root), startup_timeout=30)
        async with use_shell_session(config) as shell:
            # 1. Inspect the initial directory and the cached snapshot.
            assert Path(await shell.get_cwd()) == root
            assert shell.snapshot().cwd == str(root)

            # 2. Navigate relatively, then let a child process inherit the cwd.
            await shell.chdir("project with spaces")
            assert Path(await shell.get_cwd()) == child
            command = ProcessCommand(sys.executable, ("-c", "import os; print(os.getcwd())"))
            result = await shell.run(command, check=True)
            assert Path(result.stdout_str().strip()) == child
            await shell.chdir("..")
            assert Path(await shell.get_cwd()) == root
            assert Path.cwd() == parent_cwd
            print("Only the shell moved; Python stayed in", parent_cwd)
        # Close the shell before removing directories it may still have open.


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
