from collections.abc import Callable

import pytest

from shell_next import Backend, BackendStatus, CommandResult, Outcome, OutputResult


@pytest.fixture(params=["stdout", "stderr"])
def decode_tail(request: pytest.FixtureRequest) -> Callable[..., str]:
    output = OutputResult(tail=b"\xe9", path="capture-file-must-not-be-read")
    result = CommandResult(
        "session",
        "command",
        Backend.BASH,
        "process",
        Outcome.EXITED,
        True,
        BackendStatus(0),
        0.0,
        1.0,
        stdout=output,
        stderr=output,
    )
    assert result.command is None  # Existing manual construction remains compatible.
    return result.stdout_str if request.param == "stdout" else result.stderr_str


def test_text_decoding_policy_and_raw_bytes(decode_tail: Callable[..., str]) -> None:
    assert decode_tail() == "\ufffd"
    assert decode_tail(encoding="latin-1") == "é"
    assert decode_tail(errors="ignore") == ""
    with pytest.raises(UnicodeDecodeError):
        decode_tail(errors="strict")
    with pytest.raises(LookupError):
        decode_tail(encoding="unknown-codec")
    with pytest.raises(LookupError):
        decode_tail(errors="unknown-handler")
