"""FIFO lease acquisition that remains interruptible before a command starts."""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle


async def acquire_lease(handle: CommandHandle) -> bool:
    """Acquire exclusive execution or cancel a queued command without waiting for its predecessor.

    :param handle: Registered command waiting for execution ownership.
    :returns: Whether this caller now owns the session's execution lease.
    :raises TimeoutError: The independent acquisition deadline elapsed.
    """
    lease = handle.session.lease
    if handle.stop_requested.is_set():
        return False
    budget = handle.options.timeouts.acquire
    if next(iter(handle.session.pending), None) == handle.command_id and not lease.locked():
        async with asyncio.timeout(budget):
            return await lease.acquire()
    if handle.session.virtual_time and budget is not None:
        raise TimeoutError("Virtual acquisition deadline expired")
    acquisition = asyncio.create_task(lease.acquire())
    stopped = asyncio.create_task(handle.stop_requested.wait())
    acquired = False
    try:
        async with asyncio.timeout(budget):
            await asyncio.wait((acquisition, stopped), return_when=asyncio.FIRST_COMPLETED)
        if acquisition.done():
            acquired = acquisition.result()
        return acquired
    finally:
        acquisition.cancel()
        stopped.cancel()
        await asyncio.gather(acquisition, stopped, return_exceptions=True)
        if not acquired and not acquisition.cancelled():
            lease.release()
