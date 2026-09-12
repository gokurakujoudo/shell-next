# Interactive input and live events

All three backends support business stdin and literal prompts in stdout/stderr.
The program below prints a newline-free prompt and waits for EOF before answering.

1. Select `StdinMode.MANUAL`, enter `shell.command()`, wait for the prompt, send
   bytes and a line, then close stdin and await the final result. `sendline()`
   appends LF; `send()` does not. Input counters describe submission, not proof
   that the child consumed the bytes.
2. Replace manual decisions with an `InputPlan`: `Expect`, `SendLine`, then
   `CloseStdin`. `Send` is available when no newline is wanted. A plan owns the
   writer exclusively; do not mix it with manual sends.
3. Observe `handle.events()` in a sibling task while completing the dialogue.
   Read stream names, offsets, and raw chunks. The final result still contains
   captured output even if the subscriber missed early chunks.

Events are future-only, bounded, and do not replay earlier output. Slow readers
receive `OutputSubscriberError`; primary capture keeps working. Stdout/stderr
have independent ordering. The example consumes events to completion within a
`TaskGroup`, so neither the reader nor command outlives its owning scope.

Prompt matching is literal bytes, including split chunks, not regular expressions.
Use `stream='stderr'` or `stream='either'` for other prompt locations. A timeout
limits waiting for the prompt. Terminal/full-screen applications and PowerShell
Host prompts are unsupported. Use `secret=True` on input steps or manual sends
to redact mock history; do not put secrets in command text or print them.

## Full example

File: [`examples/06-input-and-events.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/06-input-and-events.py).

```console
python examples/06-input-and-events.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 06-input-and-events.py -->
```python
"""Answer prompts manually, automate a dialogue, and observe live output."""

import asyncio
import os
import sys

from shell_next import (
    Backend,
    CloseStdin,
    CommandHandle,
    CommandOptions,
    Expect,
    InputPlan,
    ProcessCommand,
    SendLine,
    SessionConfig,
    StdinMode,
    use_shell_session,
)


async def display_events(handle: CommandHandle) -> None:
    async for event in handle.events():
        print(event.stream, event.offset, event.data)


async def main(backend: Backend) -> None:
    # Read until EOF so close_stdin has a clear role in every dialogue.
    command = ProcessCommand(
        sys.executable,
        (
            "-u",
            "-c",
            "import sys; print('Name: ', end='', flush=True); "
            "name=sys.stdin.read().strip(); print('Hello, ' + name)",
        ),
    )
    config = SessionConfig(backend=backend, startup_timeout=30)
    async with use_shell_session(config) as shell:
        # 1. The command scope owns cleanup while the caller writes input.
        options = CommandOptions(stdin=StdinMode.MANUAL)
        async with shell.command(command, options=options, check=True, timeout=10) as handle:
            await handle.expect(b"Name: ", timeout=5)
            await handle.send(b"Ad")
            await handle.sendline(b"a")
            await handle.close_stdin()
            result = await handle.wait()
        assert "Hello, Ada" in result.stdout_str()
        assert result.input.submitted == 4

        # 2. The input plan becomes the sole writer for a known dialogue.
        options = CommandOptions(
            stdin=StdinMode.PLAN,
            input_plan=InputPlan((Expect(b"Name: ", timeout=5), SendLine(b"Ada"), CloseStdin())),
        )
        result = await shell.run(command, options=options, check=True, timeout=10)
        assert "Hello, Ada" in result.stdout_str()

        # 3. Subscribe while interacting; final capture remains authoritative.
        options = CommandOptions(stdin=StdinMode.MANUAL)
        async with shell.command(command, options=options, check=True, timeout=10) as handle:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(display_events(handle))
                await handle.expect(b"Name: ", timeout=5)
                await handle.sendline(b"Grace")
                await handle.close_stdin()
                result = await handle.wait()
        assert "Hello, Grace" in result.stdout_str()


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
