"""Bounded subscribers and rolling literal match windows."""

import asyncio
from collections.abc import AsyncIterator, Callable

from shell_next.errors import ConfigurationError, InputError, OutputSubscriberError
from shell_next.models.config import CaptureConfig
from shell_next.models.input import MatchStream, StreamName
from shell_next.models.results import OutputEvent


class OutputHub:
    """Keep independent capture notifications without consumer backpressure.

    :param command_id: Owning command identifier.
    :param config: Matching-window and subscriber bounds.
    :param clock: Monotonic or virtual clock callable, in seconds.
    """

    def __init__(self, command_id: str, config: CaptureConfig, clock: Callable[[], float]) -> None:
        """Create bounded windows without background tasks.

        :param command_id: Owning command identifier.
        :param config: Bounds for retained matching data and subscriber events.
        :param clock: Timestamp source, in seconds.
        """
        self.command_id = command_id
        self.config = config
        self.clock = clock
        self.windows: dict[StreamName, bytes] = {"stdout": b"", "stderr": b"", "terminal": b""}
        self.offsets: dict[StreamName, int] = {"stdout": 0, "stderr": 0, "terminal": 0}
        self.cursors: dict[StreamName, int] = {"stdout": 0, "stderr": 0, "terminal": 0}
        self.sequence = 0
        self.changed = asyncio.Event()
        self.closed = False
        self.subscribers: set[asyncio.Queue[OutputEvent | Exception | None]] = set()

    def publish(self, stream: StreamName, data: bytes) -> None:
        """Notify subscribers after primary capture has accepted a chunk.

        :param stream: Source transport.
        :param data: Raw chunk bytes.
        """
        event = OutputEvent(
            self.command_id, self.sequence, stream, self.offsets[stream], data, self.clock()
        )
        self.sequence += 1
        self.offsets[stream] += len(data)
        self.windows[stream] = (self.windows[stream] + data[-self.config.match_bytes :])[
            -self.config.match_bytes :
        ]
        self.changed.set()
        for queue in tuple(self.subscribers):
            if queue.full():
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(OutputSubscriberError("Output subscription overflowed"))
                self.subscribers.remove(queue)
            else:
                queue.put_nowait(event)

    def finish(self) -> None:
        """Wake prompt waiters and terminate subscribers without blocking capture."""
        self.closed = True
        self.changed.set()
        for queue in self.subscribers:
            if queue.full():
                queue.get_nowait()
                queue.put_nowait(OutputSubscriberError("Output subscription overflowed"))
            else:
                queue.put_nowait(None)
        self.subscribers.clear()

    async def events(self) -> AsyncIterator[OutputEvent]:
        """Subscribe to future chunks; leaving the iterator never stops execution.

        :returns: An asynchronous iterator over future raw output events.
        :raises OutputSubscriberError: The subscriber's bounded queue overflows.
        """
        queue: asyncio.Queue[OutputEvent | Exception | None] = asyncio.Queue(
            self.config.event_queue
        )
        if self.closed:
            return
        self.subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                if isinstance(event, Exception):
                    raise event
                yield event
        finally:
            self.subscribers.discard(queue)

    async def expect(self, pattern: bytes, stream: MatchStream, timeout: float | None) -> bytes:
        """Match a literal across chunks, consuming matches in each stream independently.

        :param pattern: Nonempty literal fitting the configured rolling window.
        :param stream: stdout, stderr, or either independent stream.
        :param timeout: Observation deadline in seconds, or None.
        :returns: The matching literal bytes.
        :raises ConfigurationError: The requested pattern cannot fit the window.
        :raises InputError: The stream ended without a match.
        :raises TimeoutError: This observation deadline elapsed.
        """
        if not pattern or len(pattern) > self.config.match_bytes:
            raise ConfigurationError("Pattern must fit the nonempty matching window")
        streams: tuple[StreamName, ...] = ("stdout", "stderr") if stream == "either" else (stream,)
        async with asyncio.timeout(timeout):
            while True:
                self.changed.clear()
                for name in streams:
                    window = self.windows[name]
                    base = self.offsets[name] - len(window)
                    index = window.find(pattern, max(0, self.cursors[name] - base))
                    if index >= 0:
                        self.cursors[name] = base + index + len(pattern)
                        return pattern
                if self.closed:
                    raise InputError("Output ended before the expected prompt")
                await self.changed.wait()
