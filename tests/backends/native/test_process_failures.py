import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from shell_next import Backend, SessionConfig
from shell_next.backends.native import process as native_process
from shell_next.backends.native.process import NativeProcess
from shell_next.errors import CapabilityError, SessionStartupError
from tests.support.native import FakeContainment, FakeProcess


def config() -> SessionConfig:
    return SessionConfig(Backend.CMD if sys.platform == "win32" else Backend.BASH)


@pytest.mark.parametrize("mode", ["missing", "eof", "containment", "diagnostic"])
async def test_startup_failures_retain_process_ownership(
    mode: str,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeProcess(handshake=mode != "eof", diagnostic=mode == "diagnostic")
    monkeypatch.setattr(tempfile, "tempdir", str(directory))

    async def create(*args: object, **kwargs: object) -> FakeProcess:
        if mode == "missing":
            raise FileNotFoundError("missing shell")
        return process

    def contain(process: FakeProcess) -> FakeContainment:
        if mode == "containment":
            raise OSError("cannot contain")
        return FakeContainment(process)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(native_process, "create_containment", contain)
    native = NativeProcess(config())
    with pytest.raises(SessionStartupError):
        await native.start()
    assert native.process is None and native.directory is None
    assert mode == "missing" or process.killed
    assert not await asyncio.to_thread(lambda: list(directory.iterdir()))


async def test_cancellation_during_creation_adopts_and_stops_child(
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = asyncio.Event()
    release = asyncio.Event()
    process = FakeProcess()
    monkeypatch.setattr(tempfile, "tempdir", str(directory))

    async def create(*args: object, **kwargs: object) -> FakeProcess:
        created.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    native = NativeProcess(config())
    owner = asyncio.create_task(native.start())
    await created.wait()
    owner.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await owner
    assert process.killed and native.directory is None


async def test_incompatible_platform_fails_before_allocating_resources() -> None:
    backend = Backend.BASH if sys.platform == "win32" else Backend.CMD
    native = NativeProcess(SessionConfig(backend))
    with pytest.raises(CapabilityError):
        await native.start()
    assert native.directory is None


@pytest.mark.parametrize("running,wait_failure", [(True, False), (False, False), (False, True)])
async def test_shutdown_reports_wait_and_directory_errors(
    running: bool, wait_failure: bool
) -> None:
    process = FakeProcess()
    process.returncode = None if running else 0
    if wait_failure:
        process.wait_error = TimeoutError()

    class Directory:
        def cleanup(self) -> None:
            raise OSError("cannot remove capture directory")

    native = NativeProcess(config())
    native.process = cast(Any, process)
    native.directory = cast(Any, Directory())
    result = await native.close()
    assert not result.contained and "OSError" in result.errors
    assert ("TimeoutError" in result.errors) is wait_failure
    assert native.process is None and native.directory is None
    assert process.killed is running
