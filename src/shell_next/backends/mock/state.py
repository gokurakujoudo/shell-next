"""Virtual state access through the common lifecycle and execution lease."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from shell_next.frontend.observation import checkpoint

if TYPE_CHECKING:
    from shell_next.frontend.session import ShellSession


@asynccontextmanager
async def state_access(session: ShellSession) -> AsyncIterator[None]:
    """Serialize a virtual state operation after previously submitted command work.

    :param session: Owning mock session with normal concurrency configuration.
    :returns: Scope holding the session's execution lease.
    :raises SessionError: Lifecycle, busy, or reentrancy validation fails.
    """
    session.validate_submission()
    await checkpoint()
    async with session.lease:
        session.validate_submission()
        yield
