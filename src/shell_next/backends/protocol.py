"""Transport contract implemented by native interpreters and in-memory scenarios."""

from typing import TYPE_CHECKING, Protocol

from shell_next.models.commands import Command
from shell_next.models.results import BackendStatus, CleanupReport

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle


class SessionDriver(Protocol):
    """Resource-owning execution adapter; the frontend supplies lifecycle policy."""

    async def start(self) -> None:
        """Acquire backend resources before the session becomes usable."""
        ...

    def reserve(self, command: Command) -> object | None:
        """Validate and reserve a submitted command.

        :param command: Structural process or native script.
        :returns: Optional driver-owned reservation data.
        """
        ...

    async def prepare(self, handle: CommandHandle) -> None:
        """Prepare command resources while owning the execution lease.

        :param handle: Owning command handle.
        """
        ...

    async def execute(self, handle: CommandHandle) -> BackendStatus:
        """Run the prepared command and drain output.

        :param handle: Command receiving readiness and output.
        :returns: Backend-native status.
        """
        ...

    async def send(self, data: bytes) -> None:
        """Submit one input transport operation.

        :param data: Raw business input bytes.
        """
        ...

    async def close_stdin(self) -> None:
        """Close business input independently of shell control input."""
        ...

    async def finish(self) -> None:
        """Release command-specific resources after execution or termination."""
        ...

    async def stop(self) -> CleanupReport:
        """Stop active execution and preserve process ownership.

        :returns: Termination and containment evidence.
        """
        ...

    async def close(self) -> CleanupReport:
        """Close all backend resources idempotently.

        :returns: Session shutdown evidence.
        """
        ...
