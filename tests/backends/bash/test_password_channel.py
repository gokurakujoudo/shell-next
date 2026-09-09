from typing import Any, cast

import pytest

from shell_next import (
    CommandOptions,
    MockShellSession,
    PrivilegeRequest,
    ProcessCommand,
    SessionConfig,
)
from shell_next.backends.bash.password_channel import supply_passwords
from shell_next.errors import PrivilegeAuthenticationError
from shell_next.frontend.handle import CommandHandle


class InputChannel:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def read(self, size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""


class OutputChannel:
    async def send(self, data: bytes) -> None:
        assert data.endswith(b"\n")


async def test_fragmented_private_prompt_and_eof() -> None:
    calls = 0

    async def provider() -> bytes:
        nonlocal calls
        calls += 1
        return b"value"

    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated",
            interactive=True,
            password_provider=provider,
        )
    )
    handle = CommandHandle(
        MockShellSession(SessionConfig()), "command", ProcessCommand("virtual"), options
    )
    await supply_passwords(
        handle, cast(Any, InputChannel([b"pass", b"word\n"])), cast(Any, OutputChannel())
    )
    assert calls == 1


@pytest.mark.parametrize(
    "chunks,password",
    [
        ([b"x" * 129], b"value"),
        ([b"unexpected\n"], b"value"),
        ([b"password\npassword\n"], b"value"),
        ([b"password\n"], b"bad\nvalue"),
    ],
)
async def test_malformed_private_requests_and_invalid_secrets_are_rejected(
    chunks: list[bytes],
    password: bytes,
) -> None:
    async def provider() -> bytes:
        return password

    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated", interactive=True, password_provider=provider
        )
    )
    session = MockShellSession(SessionConfig())
    handle = CommandHandle(session, "command", ProcessCommand("virtual"), options)
    with pytest.raises(PrivilegeAuthenticationError):
        await supply_passwords(handle, cast(Any, InputChannel(chunks)), cast(Any, OutputChannel()))
