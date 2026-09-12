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
