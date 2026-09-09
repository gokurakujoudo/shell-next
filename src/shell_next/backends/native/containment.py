"""Dispatch containment to the selected operating-system domain."""

import asyncio
import sys

from shell_next.backends.bash.containment import PosixGroup
from shell_next.backends.windows.containment import WindowsJob


def create_containment(process: asyncio.subprocess.Process) -> PosixGroup | WindowsJob:
    """Contain an idle shell before any user-controlled command executes.

    :param process: Newly created persistent interpreter.
    :returns: Process-group or Job Object containment owner.
    :raises OSError: The operating system rejects containment assignment.
    """
    return WindowsJob(process) if sys.platform == "win32" else PosixGroup(process.pid)
