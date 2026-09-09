import ctypes
import os
import sys
from typing import Any, cast

import pytest

from shell_next.backends.bash.containment import PosixGroup
from shell_next.backends.windows.containment import WindowsJob
from tests.support.native import FakeKernel, FakeProcess


@pytest.mark.parametrize(
    "failed",
    ["CreateJobObjectW", "OpenProcess", "SetInformationJobObject", "AssignProcessToJobObject"],
)
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object failure boundaries")
async def test_job_assignment_failures_close_owned_handles(
    failed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel = FakeKernel()
    getattr(kernel, failed).result = 0
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    with pytest.raises(OSError):
        WindowsJob(cast(Any, FakeProcess()))
    if failed != "CreateJobObjectW":
        assert kernel.CloseHandle.calls


async def test_job_close_is_idempotent_and_termination_failure_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = FakeKernel()
    if sys.platform == "win32":
        monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    job = WindowsJob(cast(Any, FakeProcess()))
    if sys.platform == "win32":
        kernel.TerminateJobObject.result = 0
        with pytest.raises(OSError):
            job.terminate()
    job.close()
    job.close()
    job.terminate()


def test_process_group_stop_tolerates_an_already_exited_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def gone(*args: object) -> None:
        raise ProcessLookupError()

    if sys.platform != "win32":
        monkeypatch.setattr(os, "killpg", gone)
    group = PosixGroup(99999999)
    group.terminate()
    group.close()
