"""Command-specific byte pipes; no shell control bytes share business input."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, cast


class CommandChannel:
    """One named pipe endpoint, using Windows IOCP or a POSIX FIFO.

    :param path: Private pipe name or FIFO path.
    :param input_channel: True when the package writes business input.
    """

    def __init__(self, path: str, input_channel: bool = False) -> None:
        """Initialize endpoint ownership without creating operating-system resources.

        :param path: Private endpoint name.
        :param input_channel: Whether this endpoint supplies stdin.
        """
        self.path = path
        self.input_channel = input_channel
        self.reader = asyncio.StreamReader()
        self.writer: asyncio.StreamWriter | None = None
        self.connected = asyncio.Event()
        self.transport: asyncio.BaseTransport | None = None
        self.servers: list[Any] = []
        self.keeper: int | None = None

    def accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Adopt the first Windows pipe client and reject additional connections.

        :param reader: Client input stream.
        :param writer: Client output stream.
        """
        if self.connected.is_set():
            writer.close()
            return
        self.reader = reader
        self.writer = writer
        self.connected.set()

    async def open(self) -> None:
        """Create a private endpoint with bounded asyncio transport buffering.

        :raises OSError: The operating system cannot create the endpoint.
        """
        loop = asyncio.get_running_loop()
        if sys.platform == "win32":

            def protocol_factory() -> asyncio.StreamReaderProtocol:
                """Build the Windows pipe server's stream adapter.

                :returns: Protocol accepting one client into this channel.
                """
                return asyncio.StreamReaderProtocol(asyncio.StreamReader(), self.accept)

            self.servers = await cast(Any, loop).start_serving_pipe(protocol_factory, self.path)
        else:
            os.mkfifo(self.path, 0o600)
            read_fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            self.keeper = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
            if self.input_channel:
                protocol = asyncio.streams.FlowControlMixin(loop=loop)
                pipe = os.fdopen(self.keeper, "wb", buffering=0)
                self.keeper = read_fd
                transport, _ = await loop.connect_write_pipe(lambda: protocol, pipe)
                self.transport = transport
                self.writer = asyncio.StreamWriter(transport, protocol, None, loop)
            else:
                pipe = os.fdopen(read_fd, "rb", buffering=0)
                read_transport, _ = await loop.connect_read_pipe(
                    lambda: asyncio.StreamReaderProtocol(self.reader), pipe
                )
                self.transport = read_transport
            self.connected.set()

    def release_keeper(self) -> None:
        """Release the POSIX bootstrap descriptor after native redirection opens."""
        if self.keeper is not None:
            os.close(self.keeper)
            self.keeper = None

    async def read(self, size: int) -> bytes:
        """Read command bytes after the shell connects the endpoint.

        :param size: Maximum bytes returned in one transport chunk.
        :returns: Bytes, or empty bytes at EOF.
        """
        await self.connected.wait()
        return await self.reader.read(size)

    async def send(self, data: bytes) -> None:
        """Submit bytes through the endpoint with transport backpressure.

        :param data: Business input bytes.
        :raises ConnectionError: The native command closed its input.
        """
        await self.connected.wait()
        assert self.writer is not None
        self.writer.write(data)
        await self.writer.drain()

    def close(self) -> None:
        """Idempotently close the endpoint and its bootstrap descriptors."""
        self.release_keeper()
        if self.writer is not None:
            self.writer.close()
        if self.transport is not None:
            self.transport.close()
        for server in self.servers:
            server.close()
        if sys.platform != "win32":
            Path(self.path).unlink(missing_ok=True)
