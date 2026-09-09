import pytest

from shell_next import (
    CommandOptions,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    Receive,
    SessionConfig,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import MockUnexpectedCommandError, MockUnexpectedInputError


@pytest.mark.parametrize(
    "expected,sent", [(None, b"unexpected"), (b"expected", None), (b"x", b"extra")]
)
async def test_eof_and_extra_input_are_strict(expected: bytes | None, sent: bytes | None) -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(expected),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        if sent is None:
            await handle.close_stdin()
        else:
            await handle.send(sent)
        with pytest.raises(MockUnexpectedInputError):
            await handle.wait()


async def test_trailing_input_after_matching_prefix_is_rejected() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"x"),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await handle.send(b"xy")
        with pytest.raises(MockUnexpectedInputError):
            await handle.wait()


def test_out_of_order_commands_do_not_consume_expectations() -> None:
    command = ProcessCommand("expected")
    scenario = MockScenario([MockExpectation(command)])
    with pytest.raises(MockUnexpectedCommandError):
        scenario.reserve(ProcessCommand("wrong"))
    assert scenario.cursor == 0
    assert scenario.reserve(command).command == command
