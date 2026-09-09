import asyncio
from typing import Any


class MemoryWriter:
    def __init__(self) -> None:
        self.closed = False
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, *, handshake: bool = True, diagnostic: bool = False) -> None:
        self.pid = 99999999
        self.stdin = MemoryWriter()
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        if handshake:
            self.stdout.feed_data(b"shell-next-session-ready\n")
        self.stdout.feed_eof()
        if diagnostic:
            self.stderr.feed_data(b"wrapper failed\n")
        self.stderr.feed_eof()
        self.returncode: int | None = None
        self.killed = False
        self.wait_error: Exception | None = None

    def kill(self) -> None:
        self.killed = True
        self.returncode = -1

    async def wait(self) -> int:
        if self.wait_error is not None:
            raise self.wait_error
        self.returncode = 0
        return 0


class FakeContainment:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.closed = False
        self.signals: list[bool] = []

    def terminate(self, force: bool = True) -> None:
        self.signals.append(force)
        self.process.kill()

    def close(self) -> None:
        self.closed = True


class FakeFunction:
    def __init__(self, result: int) -> None:
        self.result = result
        self.argtypes: list[Any] = []
        self.restype: Any = None
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, *args: object) -> int:
        self.calls.append(args)
        return self.result


class FakeKernel:
    def __init__(self) -> None:
        self.CreateJobObjectW = FakeFunction(100)
        self.OpenProcess = FakeFunction(200)
        self.SetInformationJobObject = FakeFunction(1)
        self.AssignProcessToJobObject = FakeFunction(1)
        self.TerminateJobObject = FakeFunction(1)
        self.CloseHandle = FakeFunction(1)
