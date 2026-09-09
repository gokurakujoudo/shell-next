import asyncio

import pytest

from shell_next import CommandOptions, MockShellSession, ProcessCommand, SessionConfig
from shell_next.frontend.handle import CommandHandle
from shell_next.frontend.lease import acquire_lease


async def test_cancelled_observer_releases_a_concurrently_acquired_lease() -> None:
    session = MockShellSession(SessionConfig())
    handle = CommandHandle(session, "queued", ProcessCommand("virtual"), CommandOptions())
    await session.lease.acquire()
    acquiring = asyncio.create_task(acquire_lease(handle))
    # Lock acquisition completes in the same turn as owner cancellation.
    from shell_next.frontend.observation import checkpoint

    await checkpoint()
    session.lease.release()
    asyncio.get_running_loop().call_soon(acquiring.cancel)
    with pytest.raises(asyncio.CancelledError):
        await acquiring
    assert not session.lease.locked()
