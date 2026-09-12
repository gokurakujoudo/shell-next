# Queued and concurrent work

One session executes one command at a time so cwd and environment have a clear
order. These two examples work on Bash, PowerShell, and cmd.

1. Configure `ConcurrencyPolicy.QUEUE`, submit two commands synchronously, then
   await their handles. Both are registered immediately and execute FIFO. The
   session owns them even before you wait. Queueing does not run them in parallel.
2. Start independent sessions in a Python `TaskGroup`. Each task owns its session
   scope, so failures or cancellation still unwind the resources it created.

The default policy is `REJECT`: a second command while one is active raises
`SessionBusyError`. Never acquire the same session recursively inside a live
command context, even with `QUEUE`; this raises `SessionReentrancyError` rather
than deadlocking. Parallelism belongs across sessions. A coroutine that has not
been awaited or scheduled is not a submission; use `submit()` for start-now work.

## Full example

File: [`examples/08-concurrency.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/08-concurrency.py).

```console
python examples/08-concurrency.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 08-concurrency.py -->
```python
"""Queue work on one session or run independent sessions concurrently."""

import asyncio
import os
import sys

from shell_next import (
    Backend,
    ConcurrencyPolicy,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)


async def independent(backend: Backend, label: str) -> str:
    async with use_shell_session(SessionConfig(backend=backend, startup_timeout=30)) as shell:
        command = ProcessCommand(sys.executable, ("-c", "import sys; print(sys.argv[1])", label))
        result = await shell.run(command, check=True, timeout=10)
        return result.stdout_str().strip()


async def main(backend: Backend) -> None:
    # 1. submit() registers both immediately; QUEUE executes in FIFO order.
    config = SessionConfig(backend=backend, concurrency=ConcurrencyPolicy.QUEUE, startup_timeout=30)
    async with use_shell_session(config) as shell:
        first = shell.submit(ProcessCommand(sys.executable, ("-c", "print('first')")), check=True)
        second = shell.submit(ProcessCommand(sys.executable, ("-c", "print('second')")), check=True)
        results = await asyncio.gather(first.wait(), second.wait())
        assert [result.stdout_str().strip() for result in results] == ["first", "second"]

    # 2. Each concurrent task owns its own session and its cleanup scope.
    async with asyncio.TaskGroup() as tasks:
        left = tasks.create_task(independent(backend, "left"))
        right = tasks.create_task(independent(backend, "right"))
    assert (left.result(), right.result()) == ("left", "right")
    print(left.result(), right.result())


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
