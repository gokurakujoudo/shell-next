import asyncio

import pytest

from shell_next import (
    Backend,
    CommandOptions,
    ConcurrencyPolicy,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    Receive,
    SessionConfig,
    StdinMode,
)
from shell_next.errors import ConfigurationError, SessionBusyError, SessionClosedError
from shell_next.frontend.observation import checkpoint


async def test_windows_virtual_paths_and_environment_validation() -> None:
    async with MockShellSession(SessionConfig(Backend.CMD)) as shell:
        await shell.chdir(r"C:\project")
        await shell.chdir(r"child\..\build")
        assert await shell.get_cwd() == r"C:\project\build"
        with pytest.raises(ConfigurationError):
            await shell.unset_env("bad=name")
    with pytest.raises(SessionClosedError):
        await shell.set_env("AFTER_CLOSE", "forbidden")


@pytest.mark.parametrize("queued", [True, False])
async def test_virtual_state_operations_use_the_execution_lease(queued: bool) -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"go"),))])
    config = SessionConfig(
        concurrency=ConcurrencyPolicy.QUEUE if queued else ConcurrencyPolicy.REJECT
    )
    async with MockShellSession(config, scenario) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        if queued:
            mutation = asyncio.create_task(shell.set_env("AFTER", "done"))
            await checkpoint()
            assert not mutation.done() and "AFTER" not in shell.environment
        else:
            with pytest.raises(SessionBusyError):
                await shell.set_env("AFTER", "forbidden")
        await handle.send(b"go")
        assert (await handle.wait()).success
        if queued:
            await mutation
            assert await shell.get_env("AFTER") == "done"
