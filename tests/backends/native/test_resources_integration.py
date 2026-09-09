import asyncio
import gc
import os
import sys
import threading
from pathlib import Path

import pytest

from shell_next import CaptureConfig, Outcome, ProcessCommand, use_shell_session
from shell_next.errors import CommandStartupError
from tests.support.sessions import BACKENDS, config_for, python_command


def resource_count() -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        count = wintypes.DWORD()
        assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count))
        return count.value
    return len(os.listdir("/proc/self/fd"))


async def settle_callbacks() -> None:
    for _ in range(5):
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().call_soon(future.set_result, None)
        await future
    gc.collect()


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_repeated_sessions_release_resources(backend: str, directory: Path) -> None:
    async with use_shell_session(config_for(backend, directory)) as warm:
        assert await warm.ping()
    await settle_callbacks()
    baseline = resource_count()
    tasks = set(asyncio.all_tasks())
    for _ in range(6):
        async with use_shell_session(config_for(backend, directory)) as shell:
            assert (await shell.run(python_command("print('done')"), timeout=10)).success
        assert not shell.pending and not shell.tasks
    await settle_callbacks()
    assert set(asyncio.all_tasks()) <= tasks
    assert resource_count() <= baseline + 2
    assert not any(thread.name.startswith("shell-capture") for thread in threading.enumerate())


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_optional_full_capture_files(backend: str, directory: Path) -> None:
    config = config_for(backend, directory)
    config.capture = CaptureConfig(tail_bytes=16, directory=directory)
    async with use_shell_session(config) as shell:
        result = await shell.run(python_command("import os; os.write(1,b'raw'*10000)"), timeout=10)
        assert result.stdout.complete and result.stderr.complete
        assert result.stdout.committed == result.stdout.received == 30000
        assert result.stdout.path is not None and result.stderr.path is not None
        data = await asyncio.to_thread(Path(result.stdout.path).read_bytes)
        assert data == b"raw" * 10000
        empty = await asyncio.to_thread(Path(result.stderr.path).read_bytes)
        assert empty == b""


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_missing_executable_reports_startup_failure(backend: str, directory: Path) -> None:
    async with use_shell_session(config_for(backend, directory)) as shell:
        with pytest.raises(CommandStartupError) as failure:
            await shell.run(
                ProcessCommand(str(directory / "does-not-exist")), check=True, timeout=10
            )
        assert failure.value.result.outcome == Outcome.STARTUP_FAILURE
        assert shell.is_usable
