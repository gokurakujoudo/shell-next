import pytest

from shell_next import (
    CaptureConfig,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    SessionConfig,
)
from shell_next.errors import ConfigurationError, SessionProtocolError
from shell_next.frontend.operations import state_operation


@pytest.mark.parametrize("name,value", [("bad=name", "value"), ("VALID", "bad\0value")])
async def test_invalid_state_mutations_fail_before_command_submission(
    name: str, value: str
) -> None:
    scenario = MockScenario()
    async with MockShellSession(SessionConfig(), scenario) as shell:
        with pytest.raises(ConfigurationError):
            await state_operation(shell, "set_env", name, value)
        assert scenario.cursor == 0


async def test_state_query_rejects_truncated_capture() -> None:
    import sys

    from shell_next import ProcessCommand

    command = ProcessCommand(
        sys.executable, ("-c", "import os,json; print(json.dumps(os.getcwd()))")
    )
    scenario = MockScenario([MockExpectation(command, (Emit(b'"/directory"\n'),))])
    async with MockShellSession(
        SessionConfig(capture=CaptureConfig(tail_bytes=1)), scenario
    ) as shell:
        with pytest.raises(SessionProtocolError):
            await state_operation(shell, "get_cwd")
