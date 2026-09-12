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
