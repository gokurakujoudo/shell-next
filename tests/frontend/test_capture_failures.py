import asyncio
import os
from pathlib import Path
from typing import Any, cast

import pytest

from shell_next import CaptureConfig
from shell_next.errors import OutputSubscriberError
from shell_next.frontend.capture import StreamCapture
from shell_next.frontend.finalization import seal_capture
from shell_next.frontend.output import OutputHub


async def test_partial_file_write_never_overstates_durable_bytes(directory: Path) -> None:
    path = directory / "partial"
    file = path.open("wb")

    class PartialWriter:
        def write(self, data: bytes) -> int:
            return file.write(data[:2])

        def __getattr__(self, name: str) -> Any:
            return getattr(file, name)

    capture = StreamCapture(CaptureConfig(), path)
    capture.file = cast(Any, PartialWriter())
    await capture.feed(b"abcdef")
    result = await capture.seal()
    assert result.received == 6 and result.committed == 2
    assert not result.complete and not result.sealed
    assert path.read_bytes() == b"ab"


async def test_sync_failure_closes_file_and_reports_unsealed(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(descriptor: int) -> None:
        raise OSError("disk sync failed")

    capture = StreamCapture(CaptureConfig(), directory / "output")
    await capture.feed(b"data")
    monkeypatch.setattr(os, "fsync", fail)
    result = await capture.seal()
    assert not result.sealed and result.committed == 0
    assert capture.file is not None and capture.file.closed


async def test_finalization_deadline_returns_incomplete_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blocked(self: StreamCapture, forced: bool = False) -> Any:
        await asyncio.Event().wait()

    capture = StreamCapture(CaptureConfig())
    await capture.feed(b"tail")
    monkeypatch.setattr(StreamCapture, "seal", blocked)
    result = await seal_capture(capture, False, 0)
    assert result.tail == b"tail"
    assert not result.sealed and not result.complete
    assert capture.error == "TimeoutError"


async def test_finishing_a_full_subscriber_queue_reports_overflow() -> None:
    hub = OutputHub("c", CaptureConfig(event_queue=1), lambda: 0.0)
    iterator = hub.events()
    first = asyncio.ensure_future(anext(iterator))
    checkpoint: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    asyncio.get_running_loop().call_soon(checkpoint.set_result, None)
    await checkpoint
    hub.publish("stdout", b"first")
    await first
    hub.publish("stdout", b"unread")
    hub.finish()
    with pytest.raises(OutputSubscriberError):
        await anext(iterator)
