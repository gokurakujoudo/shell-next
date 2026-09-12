# Failures, observation deadlines, and stopping

Distinguish process failure from observation timeout and actual termination.
These examples run on all three backends without relying on arbitrary sleeps.

1. Inspect a normal exit code of 7 with `check=False` (the default), then repeat
   with `check=True` and catch `CommandFailedError`. The exception carries the
   already-finalized result. PowerShell native scripts also expose
   `last_success`, `native_exit_code`, and `terminating_error` in `result.status`.
2. Start a program waiting for EOF. A zero-second `wait_timeout` expires only
   this observation; close stdin afterward and the same command succeeds.
   `ping()` executes a health check; `snapshot()` and repr only read cached state.
3. Stop another waiting program explicitly with `handle.stop()`. Inspect cleanup
   and `session_reusable`, then close the session instead of assuming reuse.

`timeout=10` bounds command execution, including input waiting. For independent
budgets use `CommandOptions(timeouts=TimeoutPolicy(execution=30, acquire=5,
drain=2))`. Timeout initiates cleanup; it is not an exact return-time guarantee.
With `check=True`, an execution deadline raises `CommandTimeoutError`, and an
explicit stop observed through a checked wait raises `CommandStoppedError`.
The mocking chapter demonstrates an execution timeout without real delays.

Cancelling `handle.wait()` cancels observation only. Cancelling `shell.run()`
or letting cancellation/another exception escape a command scope requests
termination because that scope owns the work. Forceful cleanup breaks the
session; create a new one explicitly. The outer context closes all owned work;
`aclose()` also supports explicit, idempotent closure when a context is unsuitable.

## Full example

File: [`examples/07-errors-and-lifecycle.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/07-errors-and-lifecycle.py).

```console
python examples/07-errors-and-lifecycle.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 07-errors-and-lifecycle.py -->
```python
"""Inspect failures, time out an observation, and explicitly stop an owned command."""

import asyncio
import os
import sys

from shell_next import (
    Backend,
    CommandOptions,
    Outcome,
    ProcessCommand,
    SessionConfig,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import CommandFailedError


async def main(backend: Backend) -> None:
    config = SessionConfig(backend=backend, startup_timeout=30)
    async with use_shell_session(config) as shell:
        # 1. A nonzero exit is a normal EXITED outcome with success=False.
        failure = ProcessCommand(sys.executable, ("-c", "import sys; sys.exit(7)"))
        result = await shell.run(failure)
        assert result.outcome == Outcome.EXITED and not result.success
        assert result.status.code == 7
        try:
            await shell.run(failure, check=True)
        except CommandFailedError as error:
            assert error.result.command is failure
            assert error.result.status.code == 7
        else:
            raise AssertionError("check=True must report failure")

        # 2. This process waits for EOF; timing out observation does not stop it.
        command = ProcessCommand(
            sys.executable,
            ("-u", "-c", "import sys; print('ready', flush=True); sys.stdin.read(); print('done')"),
        )
        options = CommandOptions(stdin=StdinMode.MANUAL)
        async with shell.command(command, options=options, timeout=10) as handle:
            await handle.expect(b"ready", timeout=5)
            try:
                await handle.wait(wait_timeout=0)
            except TimeoutError:
                pass
            else:
                raise AssertionError("The process is still waiting for EOF")
            await handle.close_stdin()
            assert (await handle.wait()).success
        await shell.ping()
        assert shell.is_usable

        # 3. A deliberate stop finalizes cleanup; do not assume session reuse.
        async with shell.command(command, options=options, timeout=10) as handle:
            await handle.expect(b"ready", timeout=5)
            result = await handle.stop()
        assert result.outcome == Outcome.STOPPED
        print("Reusable:", result.session_reusable, "Cleanup:", result.cleanup)
        # No more commands are submitted; the outer scope closes this session.


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
