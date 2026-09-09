import asyncio
import os
import socket
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from shell_next import (
    Advance,
    BackendStatus,
    CommandOptions,
    Emit,
    Failure,
    InputPlan,
    MockExpectation,
    MockScenario,
    MockShellSession,
    Outcome,
    ProcessCommand,
    Receive,
    Send,
    SessionConfig,
    SessionScript,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import (
    ConfigurationError,
    InputError,
    MockExpectationNotConsumedError,
    MockUnexpectedCommandError,
    MockUnexpectedInputError,
)


def forbidden(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("Mock attempted a forbidden operating-system side effect")


async def test_mock_has_no_external_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Advance(60), Emit(b"done")))])
    environment = dict(os.environ)
    cwd = os.getcwd()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(asyncio, "sleep", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(os, "chdir", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    config = SessionConfig(
        env={"VIRTUAL": "one"}, _session_cls=MockShellSession.configured(scenario)
    )
    async with use_shell_session(config) as shell:
        assert await shell.ping()
        await shell.chdir("/virtual")
        assert await shell.get_cwd() == "/virtual"
        await shell.set_env("VIRTUAL", "two")
        assert await shell.get_env("VIRTUAL") == "two"
        assert await shell.get_env() == {"VIRTUAL": "two"}
        await shell.unset_env("VIRTUAL")
        assert await shell.get_env("VIRTUAL") is None
        result = await shell.run(command)
        assert result.finished == 60
        assert result.stdout.tail == b"done"
        with pytest.raises(ConfigurationError):
            await shell.set_env("bad=name", "value")
    scenario.assert_called(command)
    scenario.assert_consumed()
    assert dict(os.environ) == environment and os.getcwd() == cwd


async def test_strict_unexpected_and_unused_expectations() -> None:
    command = SessionScript("expected")
    config = SessionConfig(_session_cls=MockShellSession)
    async with use_shell_session(config) as shell:
        with pytest.raises(MockUnexpectedCommandError):
            await shell.run(command)
    scenario = MockScenario([MockExpectation(command)])
    config._session_cls = MockShellSession.configured(scenario)
    with pytest.raises(MockExpectationNotConsumedError):
        async with use_shell_session(config):
            pass
    with pytest.raises(ValueError, match="original"):
        async with use_shell_session(config):
            raise ValueError("original")


async def test_permissive_mock_and_state_changes() -> None:
    command = SessionScript("simulated")
    expectation = MockExpectation(command, cwd="/changed", env=(("new", "value"), ("old", None)))
    scenario = MockScenario([expectation], strict=False)
    config = SessionConfig(env={"old": "value"}, _session_cls=MockShellSession.configured(scenario))
    async with use_shell_session(config) as shell:
        assert (await shell.run(command)).success
        assert shell.snapshot().cwd == "/changed"
        assert shell.snapshot().environment == (("new", "value"),)
        assert (await shell.run(SessionScript("anything"))).success


async def test_input_mismatch_and_secret_history_redaction() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"expected"),))])
    config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
    async with use_shell_session(config) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await handle.send(b"secret-wrong-value", secret=True)
        with pytest.raises(MockUnexpectedInputError):
            await handle.wait()
    assert "secret-wrong-value" not in repr(scenario.calls)
    assert "<redacted>" in repr(scenario.calls)


@pytest.mark.parametrize(
    "failure,outcome",
    [
        (Failure("input"), Outcome.INPUT_FAILURE),
        (Failure("output"), Outcome.OUTPUT_FAILURE),
        (Failure("startup"), Outcome.STARTUP_FAILURE),
        (Failure("session"), Outcome.SESSION_LOST),
    ],
)
async def test_simulated_failure_outcomes(failure: Failure, outcome: Outcome) -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (failure,))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        result = await shell.run(command)
        assert result.outcome == outcome and not result.success


async def test_manual_writer_rejects_plan_ownership_and_closed_input() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(None),))])
    config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
    async with use_shell_session(config) as shell:
        handle = shell.submit(command)
        with pytest.raises(InputError):
            await handle.send(b"forbidden")
        await handle.wait()
        await handle.close_stdin()
        with pytest.raises(InputError):
            await handle.write_input(b"closed", False)


async def test_mock_advance_and_native_status() -> None:
    command = SessionScript("native")
    scenario = MockScenario(
        [MockExpectation(command, (Advance(2),), BackendStatus(None, False, 8, True))]
    )
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        result = await shell.run(command, timeout=3)
        assert result.finished == 2
        assert result.status.native_exit_code == 8
        assert not result.success


async def test_plan_send_and_explicit_close() -> None:
    from shell_next import CloseStdin

    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"payload"), Receive(None)))])
    config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
    options = CommandOptions(
        stdin=StdinMode.PLAN, input_plan=InputPlan((Send(b"payload"), CloseStdin()))
    )
    async with use_shell_session(config) as shell:
        result = await shell.run(command, options=options)
        assert result.input.submitted == 7 and result.input.closed
