import asyncio

import pytest

from shell_next import (
    CommandOptions,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    Receive,
    SessionConfig,
    StdinMode,
    use_shell_session,
)
from shell_next.frontend.observation import checkpoint


async def test_cancelled_checkpoint_does_not_leave_invalid_callback() -> None:
    task = asyncio.create_task(checkpoint())
    asyncio.get_running_loop().call_soon(task.cancel)
    with pytest.raises(asyncio.CancelledError):
        await task
    await checkpoint()


async def test_public_events_observe_output_without_owning_execution() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"go"), Emit(b"done")))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        events = handle.events()
        reading = asyncio.ensure_future(anext(events))
        await checkpoint()
        await handle.send(b"go")
        assert (await reading).data == b"done"
        assert (await handle.wait()).stdout.tail == b"done"
        with pytest.raises(StopAsyncIteration):
            await anext(events)
