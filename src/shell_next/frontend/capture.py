"""Bounded raw capture independent of optional output subscribers."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO

from shell_next.models.config import CaptureConfig
from shell_next.models.results import OutputResult


class StreamCapture:
    """Capture one stream with bounded memory and isolated optional file writes.

    :param config: Tail and destination configuration.
    :param path: Unique file path; None keeps capture entirely in memory.
    """

    def __init__(self, config: CaptureConfig, path: Path | None = None) -> None:
        """Initialize bookkeeping without opening files or starting threads.

        :param config: Capture limits.
        :param path: Optional unique file destination.
        """
        self.config = config
        self.path = path
        self.received = 0
        self.committed = 0
        self.written = 0
        self.tail = bytearray()
        self.error: str | None = None
        self.file: BinaryIO | None = None
        self.executor: ThreadPoolExecutor | None = None

    def write_file(self, data: bytes) -> None:
        """Write one bounded chunk on the capture-owned executor.

        :param data: Raw bytes for the destination.
        :raises OSError: The file cannot be opened or written.
        """
        if self.file is None:
            assert self.path is not None
            self.file = self.path.open("xb")
        written = self.file.write(data)
        self.written += written
        if written != len(data):
            raise OSError("Capture destination accepted a partial write")

    async def feed(self, data: bytes) -> None:
        """Retain the bounded tail and apply bounded backpressure to file writes.

        :param data: A bounded transport chunk.
        """
        self.received += len(data)
        if not self.config.discard and self.config.tail_bytes:
            self.tail[:] = (self.tail + data[-self.config.tail_bytes :])[-self.config.tail_bytes :]
        if self.path is not None and self.error is None:
            if self.executor is None:
                self.executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="shell-capture"
                )
            try:
                await asyncio.get_running_loop().run_in_executor(
                    self.executor, self.write_file, data
                )
            except OSError as exc:
                self.error = type(exc).__name__

    def seal_file(self) -> None:
        """Flush and sync the destination before declaring durable commitment.

        :raises OSError: Flush, sync, or close failed.
        """
        if self.file is not None:
            try:
                self.file.flush()
                os.fsync(self.file.fileno())
                self.committed = self.written
            finally:
                self.file.close()

    async def seal(self, forced: bool = False) -> OutputResult:
        """Finalize capture and report truncation or storage failures honestly.

        :param forced: Transport may still have unread bytes.
        :returns: Immutable stream accounting.
        """
        if self.path is not None and self.executor is None:
            await self.feed(b"")
        if self.executor is not None:
            try:
                await asyncio.get_running_loop().run_in_executor(self.executor, self.seal_file)
            except OSError as exc:
                self.error = type(exc).__name__
            finally:
                self.executor.shutdown(wait=False)
        truncated = self.path is None and self.received > len(self.tail)
        end = "eof"
        if truncated:
            end = "discarded" if self.config.discard else "truncated"
        if forced:
            end = "forced"
        if self.error is not None:
            end = "storage_failure"
        return OutputResult(
            self.received,
            self.committed,
            bytes(self.tail),
            str(self.path) if self.path is not None else None,
            end,
            not (truncated or forced or self.error),
            self.error is None,
            forced,
        )
