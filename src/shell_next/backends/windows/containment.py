"""Native process-group and Windows Job Object containment."""

import asyncio
import ctypes
import sys
from typing import Any

from shell_next.backends.windows.limits import ExtendedLimits


class WindowsJob:
    """Own one persistent shell's process group or kill-on-close Windows job.

    :param process: Newly created, idle shell process.
    """

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        """Assign the idle Windows shell to a job before any user command starts.

        :param process: Idle shell created in a new process group.
        :raises OSError: Job creation or assignment fails.
        """
        self.process = process
        self.job: Any = None
        self.kernel: Any = None
        if sys.platform == "win32":
            from ctypes import wintypes

            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            for name in ("CreateJobObjectW", "OpenProcess"):
                getattr(self.kernel, name).restype = wintypes.HANDLE
            self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.job = self.kernel.CreateJobObjectW(None, None)
            limits = ExtendedLimits()
            # Win32 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, dimensionless policy flag.
            limits.BasicLimitInformation.LimitFlags = 0x2000
            # JobObjectExtendedLimitInformation is Win32 information class 9.
            configured = self.kernel.SetInformationJobObject(
                self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            # Win32 PROCESS_SET_QUOTA | PROCESS_TERMINATE: minimum assignment rights.
            handle = self.kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
            if not handle:
                self.close()
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if (
                    not self.job
                    or not configured
                    or not self.kernel.AssignProcessToJobObject(self.job, handle)
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
            except BaseException:
                self.close()
                raise
            finally:
                self.kernel.CloseHandle(handle)

    def terminate(self, force: bool = True) -> None:
        """Signal the entire containment unit, including background descendants.

        :param force: Use SIGKILL on POSIX; Windows always terminates the job.
        :raises OSError: The operating system rejects termination.
        """
        if sys.platform == "win32" and self.job is not None:
            if not self.kernel.TerminateJobObject(self.job, 1):
                raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        """Release the Windows job handle after contained processes are terminated."""
        if self.job is not None:
            self.kernel.CloseHandle(self.job)
            self.job = None
