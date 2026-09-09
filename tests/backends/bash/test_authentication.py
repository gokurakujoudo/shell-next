import io
import subprocess
from typing import Any

import pytest

from shell_next.backends.bash.authentication import authenticate


class FakeSudo:
    def __init__(self, prompts: bytes, code: int) -> None:
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO(prompts)
        self.code = code

    def __enter__(self) -> FakeSudo:
        return self

    def __exit__(self, *args: object) -> None:
        self.stdin.close()
        self.stderr.close()

    def wait(self) -> int:
        return self.code


@pytest.mark.parametrize(
    "prompts,response,attempts,code,count",
    [
        (b"banner prompt", b"secret\n", 1, 0, 1),
        (b"promptprompt", b"wrong\n", 1, 1, 1),
        (b"prompt", b"incomplete", 1, 1, 0),
        (b"cached", b"", 1, 0, 0),
    ],
)
def test_private_authentication_and_limits(
    prompts: bytes,
    response: bytes,
    attempts: int,
    code: int,
    count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeSudo(prompts, code)
    requests = io.BytesIO()
    responses = io.BytesIO(response)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
    result = authenticate("root", attempts, b"prompt", requests, responses)
    assert result == (code == 0, count)
    assert requests.getvalue() in (b"", b"password\n")
    assert b"secret" not in requests.getvalue()


@pytest.mark.parametrize("target,code", [(None, 0), ("user", 1)])
def test_noninteractive_sudo(
    target: str | None, code: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert "-n" in argv and "-v" in argv
        return subprocess.CompletedProcess(argv, code)

    monkeypatch.setattr(subprocess, "run", run)
    assert authenticate(target, 1, b"prompt", None, None) == (code == 0, 0)
