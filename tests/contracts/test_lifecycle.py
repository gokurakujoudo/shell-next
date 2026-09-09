import asyncio
from pathlib import Path

import pytest

from shell_next import (
    Advance,
    CommandOptions,
    ConcurrencyPolicy,
    MockExpectation,
    Outcome,
    Receive,
    SessionState,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import SessionBrokenError, SessionClosedError
from tests.support.sessions import BACKENDS, config_for, python_command


@pytest.mark.parametrize("backend", BACKENDS)
async def test_timeout_invalidates_without_restart(backend: str, directory: Path) -> None:
    command = python_command("import time; time.sleep(60)")
    config = config_for(backend, directory, MockExpectation(command, (Advance(60),)))
    async with use_shell_session(config) as shell:
        result = await shell.run(command, timeout=0.25)
        assert result.outcome == Outcome.TIMEOUT
        assert result.cleanup.forced
        assert not result.session_reusable
        assert not shell.is_usable
        assert not result.stdout.complete
        with pytest.raises(SessionBrokenError):
            shell.submit(command)


@pytest.mark.parametrize("backend", BACKENDS)
async def test_exceptional_scope_preserves_original_exception(
    backend: str, directory: Path
) -> None:
    command = python_command("input()")
    config = config_for(backend, directory, MockExpectation(command, (Receive(b"never"),)))
    async with use_shell_session(config) as shell:
        with pytest.raises(ValueError, match="original"):
            async with shell.command(command, options=CommandOptions(stdin=StdinMode.MANUAL)):
                raise ValueError("original")
        assert not shell.is_usable


@pytest.mark.parametrize("backend", BACKENDS)
async def test_cancel_run_stops_owned_command(backend: str, directory: Path) -> None:
    command = python_command("input()")
    config = config_for(backend, directory, MockExpectation(command, (Receive(b"never"),)))
    async with use_shell_session(config) as shell:
        owner = asyncio.create_task(
            shell.run(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        )
        # Wait on readiness, not an arbitrary real-time sleep.
        loop = asyncio.get_running_loop()
        checkpoint = loop.create_future()
        loop.call_soon(checkpoint.set_result, None)
        await checkpoint
        handle = next(iter(shell.pending.values()))
        await handle.ready.wait()
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner
        assert handle.result is not None
        assert handle.result.outcome == Outcome.STOPPED
        assert not shell.is_usable


@pytest.mark.parametrize("backend", BACKENDS)
async def test_outer_session_owns_active_and_queued_commands(backend: str, directory: Path) -> None:
    command = python_command("input()")
    expectation = MockExpectation(command, (Receive(b"never"),))
    config = config_for(backend, directory, expectation, expectation)
    config.concurrency = ConcurrencyPolicy.QUEUE
    async with use_shell_session(config) as shell:
        active = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        queued = shell.submit(command)
        await active.ready.wait()
    assert active.future.done() and queued.future.done()
    assert queued.result is not None and queued.result.started is None
    assert not shell.pending
    assert shell.state == SessionState.CLOSED
    first = await shell.aclose()
    assert await shell.aclose() is first
    with pytest.raises(SessionClosedError):
        shell.submit(command)


@pytest.mark.parametrize("backend", BACKENDS)
async def test_separate_sessions_execute_concurrently(backend: str, directory: Path) -> None:
    command = python_command("input()")
    expectation = MockExpectation(command, (Receive(b"go\n"),))
    config_one = config_for(backend, directory, expectation)
    config_two = config_for(backend, directory, expectation)
    async with use_shell_session(config_one) as one, use_shell_session(config_two) as two:
        first = one.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        second = two.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await asyncio.gather(first.ready.wait(), second.ready.wait())
        await asyncio.gather(first.sendline(b"go"), second.sendline(b"go"))
        assert all(result.success for result in await asyncio.gather(first.wait(), second.wait()))
