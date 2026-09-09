import asyncio
from pathlib import Path

import pytest

from shell_next import CaptureConfig
from shell_next.errors import ConfigurationError, InputError, OutputSubscriberError
from shell_next.frontend.capture import StreamCapture
from shell_next.frontend.output import OutputHub


@pytest.mark.parametrize("discard", [False, True])
async def test_capture_limits_and_forced_closure(discard: bool) -> None:
    capture = StreamCapture(CaptureConfig(tail_bytes=3, discard=discard))
    await capture.feed(b"abcdef")
    result = await capture.seal(forced=True)
    assert result.received == 6
    assert result.tail == (b"" if discard else b"def")
    assert result.unread_possible and not result.complete


async def test_capture_file_is_complete_and_durable(directory: Path) -> None:
    path = directory / "output.bin"
    capture = StreamCapture(CaptureConfig(tail_bytes=3), path)
    await capture.feed(b"abc")
    await capture.feed(b"def")
    result = await capture.seal()
    assert result.complete and result.sealed
    assert result.committed == result.received == 6
    assert result.tail == b"def"
    assert path.read_bytes() == b"abcdef"


async def test_storage_failure_does_not_claim_complete(directory: Path) -> None:
    path = directory / "missing" / "capture"
    capture = StreamCapture(CaptureConfig(), path)
    await capture.feed(b"one")
    await capture.feed(b"two")
    result = await capture.seal()
    assert not result.complete and not result.sealed
    assert result.end == "storage_failure"
    assert result.committed == 0


async def test_discard_and_empty_stream_results() -> None:
    empty = await StreamCapture(CaptureConfig()).seal()
    assert empty.complete and empty.received == 0
    capture = StreamCapture(CaptureConfig(discard=True))
    await capture.feed(b"x")
    assert (await capture.seal()).end == "discarded"


async def test_match_split_prompt_consumes_once() -> None:
    hub = OutputHub("c", CaptureConfig(match_bytes=8), lambda: 2.0)
    hub.publish("stdout", b"Na")
    pending = asyncio.create_task(hub.expect(b"Name: ", "stdout", None))
    hub.publish("stdout", b"me: ")
    assert await pending == b"Name: "
    hub.publish("stderr", b"ready")
    assert await hub.expect(b"ready", "either", None) == b"ready"
    hub.finish()
    with pytest.raises(InputError):
        await hub.expect(b"Name: ", "stdout", None)
    assert len(hub.windows["stdout"]) <= 8
    for pattern in (b"", b"too long for window"):
        with pytest.raises(ConfigurationError):
            await hub.expect(pattern, "stdout", None)


async def test_subscriber_cancellation_and_normal_end() -> None:
    hub = OutputHub("c", CaptureConfig(), lambda: 0.0)
    events = hub.events()
    first = asyncio.ensure_future(anext(events))
    loop = asyncio.get_running_loop()
    ready: asyncio.Future[None] = loop.create_future()
    loop.call_soon(ready.set_result, None)
    await ready
    hub.publish("stdout", b"x")
    event = await first
    assert event.offset == 0 and event.sequence == 0 and event.data == b"x"
    hub.finish()
    with pytest.raises(StopAsyncIteration):
        await anext(events)
    assert [event async for event in hub.events()] == []


async def test_subscriber_overflow_never_blocks_capture() -> None:
    hub = OutputHub("c", CaptureConfig(event_queue=1), lambda: 0.0)
    events = hub.events()
    first = asyncio.ensure_future(anext(events))
    loop = asyncio.get_running_loop()
    ready: asyncio.Future[None] = loop.create_future()
    loop.call_soon(ready.set_result, None)
    await ready
    hub.publish("stdout", b"a")
    assert (await first).data == b"a"
    hub.publish("stdout", b"b")
    hub.publish("stdout", b"c")
    with pytest.raises(OutputSubscriberError):
        await anext(events)
    assert hub.offsets["stdout"] == 3
    hub.finish()
