"""Observation deadlines, including deterministic mock observations without real timers."""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle


async def checkpoint() -> None:
    """Allow already-ready tasks to run without sleeping or advancing wall-clock time."""
    loop = asyncio.get_running_loop()
    ready: asyncio.Future[None] = loop.create_future()

    callback = loop.call_soon(ready.set_result, None)
    try:
        await asyncio.shield(ready)
    finally:
        callback.cancel()


async def virtual_wait(handle: CommandHandle) -> None:
    """Resolve ready mock work or immediately expire a blocked observation.

    :param handle: Mock command being observed with a finite wait budget.
    :raises TimeoutError: The mock requires future input or a queued execution lease.
    """
    if handle.future.done():
        return
    if next(iter(handle.session.pending), None) != handle.command_id:
        raise TimeoutError("Virtual observation deadline expired while queued")
    await handle.ready.wait()
    await checkpoint()
    if handle.virtual_blocked:
        raise TimeoutError("Virtual observation deadline expired awaiting input")
