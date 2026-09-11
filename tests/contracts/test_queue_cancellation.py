from pathlib import Path

import pytest

from shell_next import (
    CommandOptions,
    ConcurrencyPolicy,
    Emit,
    MockExpectation,
    Outcome,
    Receive,
    StdinMode,
    TimeoutPolicy,
    use_shell_session,
)
from tests.support.sessions import BACKENDS, config_for, python_command


@pytest.mark.parametrize("backend", BACKENDS)
async def test_queued_stop_and_acquire_timeout_do_not_stop_active(
    backend: str,
    directory: Path,
) -> None:
    command = python_command("input()")
    next_command = python_command("print('next')")
    config = config_for(
        backend,
        directory,
        MockExpectation(command, (Receive(b"go\n"),)),
        MockExpectation(command),
        MockExpectation(command),
        MockExpectation(next_command, (Emit(b"next\n"),)),
    )
    config.concurrency = ConcurrencyPolicy.QUEUE
    async with use_shell_session(config) as shell:
        active = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await active.ready.wait()
        queued = shell.submit(command)
        result = await queued.stop()
        assert result.started is None and result.outcome == Outcome.STOPPED
        assert result.command is command
        assert result.stdout_str() == result.stderr_str() == ""
        deadline = shell.submit(command, options=CommandOptions(timeouts=TimeoutPolicy(acquire=0)))
        assert (await deadline.wait()).outcome == Outcome.TIMEOUT
        assert not active.future.done() and shell.is_usable
        last = shell.submit(next_command)
        await active.sendline(b"go")
        assert (await active.wait()).success
        assert (await last.wait()).stdout.tail.strip() == b"next"
