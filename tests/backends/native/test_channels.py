import asyncio
from typing import Any, cast

from shell_next.backends.native.channels import CommandChannel
from tests.support.native import MemoryWriter


async def test_duplicate_connection_cannot_replace_owned_input_channel() -> None:
    channel = CommandChannel("unused")
    first = MemoryWriter()
    duplicate = MemoryWriter()
    channel.accept(asyncio.StreamReader(), cast(Any, first))
    channel.accept(asyncio.StreamReader(), cast(Any, duplicate))
    assert duplicate.closed and not first.closed
    await channel.send(b"business")
    assert first.data == b"business" and not duplicate.data
    channel.close()
    assert first.closed
