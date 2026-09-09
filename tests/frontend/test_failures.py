import asyncio
from typing import Any

import pytest

from shell_next import (
    Advance,
    CommandOptions,
    Expect,
    InputPlan,
    MockExpectation,
    MockScenario,
    MockShellSession,
    Outcome,
    ProcessCommand,
    Receive,
    SessionConfig,
    StdinMode,
    use_shell_session,
)
from shell_next.backends.mock.driver import MockDriver
from shell_next.errors import (
    CommandTimeoutError,
    InputError,
    InteractionError,
    MockUnexpectedInputError,
    SessionClosedError,
)
from shell_next.frontend import execution
from shell_next.frontend.handle import CommandHandle
from shell_next.frontend.output import OutputHub


async def test_check_converts_final_timeout_result() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Advance(60),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        with pytest.raises(CommandTimeoutError) as failure:
            await shell.run(command, check=True, timeout=60)
        assert failure.value.result.finished == 60


async def test_failed_plan_still_finalizes_output() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command)])
    options = CommandOptions(
        stdin=StdinMode.PLAN, input_plan=InputPlan((Expect(b"absent", timeout=0),))
    )
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        with pytest.raises(InteractionError) as failure:
            await shell.run(command, options=options, check=True)
        assert failure.value.result.outcome == Outcome.INPUT_FAILURE
        assert failure.value.result.stdout.sealed


@pytest.mark.parametrize("error", [BrokenPipeError(), ConnectionResetError()])
async def test_input_transport_error_is_not_retried(
    error: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def send(self: MockDriver, data: bytes) -> None:
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr(MockDriver, "send", send)
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"never"),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        with pytest.raises(InputError):
            await handle.send(b"one")
        assert handle.input.state == "failed" and calls == 1
        await handle.stop()


async def test_cancelled_input_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    called = asyncio.Event()

    async def send(self: MockDriver, data: bytes) -> None:
        called.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(MockDriver, "send", send)
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"never"),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        sender = asyncio.create_task(handle.send(b"once"))
        await called.wait()
        sender.cancel()
        with pytest.raises(asyncio.CancelledError):
            await sender
        assert handle.input.accepted == 4 and handle.input.submitted == 0
        assert handle.input.state == "aborted"
        await handle.stop()


async def test_secondary_cleanup_errors_preserve_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def stop(self: MockDriver) -> Any:
        raise OSError("stop failed")

    async def finish(self: MockDriver) -> None:
        raise RuntimeError("finish failed")

    monkeypatch.setattr(MockDriver, "stop", stop)
    monkeypatch.setattr(MockDriver, "finish", finish)
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Advance(2),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        result = await shell.run(command, timeout=1)
        assert result.outcome == Outcome.TIMEOUT
        assert result.secondary_errors == ("OSError", "RuntimeError")
        assert not result.cleanup.contained


async def test_startup_failure_and_reentry_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SessionConfig(_session_cls=MockShellSession)
    async with use_shell_session(config) as shell:
        with pytest.raises(SessionClosedError):
            await shell.__aenter__()
        with pytest.raises(TypeError):
            shell.submit("not an explicit command")  # type: ignore[arg-type]

    async def start(self: MockDriver) -> None:
        raise OSError("startup failed")

    monkeypatch.setattr(MockDriver, "start", start)
    with pytest.raises(OSError):
        async with use_shell_session(config):
            pass


@pytest.mark.parametrize("late,mock_error", [(False, False), (False, True), (True, True)])
async def test_automation_failures_preserve_strict_expectations(
    late: bool,
    mock_error: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ended = asyncio.Event()
    original = OutputHub.finish

    def finish(self: OutputHub) -> None:
        original(self)
        ended.set()

    async def automate(handle: CommandHandle) -> None:
        if late:
            await ended.wait()
        if mock_error:
            raise MockUnexpectedInputError("expected failure")
        raise ValueError("automation failure")

    monkeypatch.setattr(execution, "automate_input", automate)
    monkeypatch.setattr(OutputHub, "finish", finish)
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command)])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        if mock_error:
            with pytest.raises(MockUnexpectedInputError):
                await shell.run(command)
        else:
            assert (await shell.run(command)).outcome == Outcome.INPUT_FAILURE


async def test_unexpected_driver_failure_is_finalized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def execute(self: MockDriver, handle: CommandHandle) -> Any:
        raise RuntimeError("backend fault")

    monkeypatch.setattr(MockDriver, "execute", execute)
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command)])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        result = await shell.run(command)
        assert result.outcome == Outcome.INTERNAL_FAILURE
        assert result.secondary_errors == ("RuntimeError",)
        assert result.stdout.sealed and not result.session_reusable
