"""Executed by a clean interpreter against an installed wheel, outside the source checkout."""

import asyncio
import os
import sys

from shell_next import (
    Backend,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)


async def main() -> None:
    command = ProcessCommand(sys.executable, ("-c", "import os; os.write(1,b'wheel')"))
    for backend in (Backend.CMD, Backend.POWERSHELL) if os.name == "nt" else (Backend.BASH,):
        async with use_shell_session(SessionConfig(backend)) as shell:
            result = await shell.run(command, check=True, timeout=15)
            assert result.stdout.tail == b"wheel"
    scenario = MockScenario([MockExpectation(command, (Emit(b"mock"),))])
    config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
    async with use_shell_session(config) as shell:
        assert (await shell.run(command)).stdout.tail == b"mock"


if __name__ == "__main__":
    asyncio.run(main())
