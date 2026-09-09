"""POSIX process-group termination for persistent Bash sessions."""

import os
import signal
import sys


class PosixGroup:
    """Own a process group whose leader was created with start_new_session=True.

    :param pid: Interpreter PID, also its process-group identifier.
    """

    def __init__(self, pid: int) -> None:
        """Retain the group identifier without acquiring another OS handle.

        :param pid: Native process-group leader identifier.
        """
        self.pid = pid

    def terminate(self, force: bool = True) -> None:
        """Signal every member of the interpreter's process group.

        :param force: SIGKILL if true, otherwise the cooperative SIGTERM request.
        :raises OSError: Permissions or another OS error prevent termination.
        """
        if sys.platform != "win32":
            try:
                os.killpg(self.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass

    def close(self) -> None:
        """Release bookkeeping; process-group IDs have no closeable OS handle."""
