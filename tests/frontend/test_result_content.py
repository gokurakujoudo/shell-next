from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from shell_next import (
    CaptureConfig,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    SessionConfig,
    SessionScript,
    use_shell_session,
)


async def test_original_script_and_split_character_tail() -> None:
    command = SessionScript("  echo '原始命令'\n# preserve whitespace\n")
    scenario = MockScenario(
        [
            MockExpectation(command, (Emit("A€".encode()), Emit("B€".encode(), "stderr"))),
        ]
    )
    config = SessionConfig(capture=CaptureConfig(tail_bytes=2))
    config._session_cls = MockShellSession.configured(scenario)
    async with use_shell_session(config) as shell:
        result = await shell.run(command)
    assert result.command is command
    assert command.text not in repr(result)
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).command = SessionScript("replacement")
    for output, text in ((result.stdout, result.stdout_str), (result.stderr, result.stderr_str)):
        assert output.tail == b"\x82\xac"
        assert output.received == 4 and not output.complete
        assert text() == "\ufffd\ufffd"
        with pytest.raises(UnicodeDecodeError):
            text(errors="strict")
        assert output.tail == b"\x82\xac"
