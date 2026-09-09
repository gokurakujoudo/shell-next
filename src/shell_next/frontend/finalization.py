"""Bounded output sealing with immutable fallback evidence on storage failure."""

import asyncio
from typing import TYPE_CHECKING

from shell_next.models.results import OutputResult

if TYPE_CHECKING:
    from shell_next.frontend.capture import StreamCapture
    from shell_next.frontend.handle import CommandHandle


async def seal_capture(capture: StreamCapture, forced: bool, deadline: float) -> OutputResult:
    """Seal one stream within its configured budget and retain failure accounting.

    :param capture: Stream destination and received-byte counters.
    :param forced: Whether termination may have left unread bytes.
    :param deadline: Finalization budget in seconds.
    :returns: Final stream evidence, incomplete when destination sealing fails.
    """
    try:
        async with asyncio.timeout(deadline):
            return await capture.seal(forced)
    except Exception as exc:
        capture.error = type(exc).__name__
        return OutputResult(
            capture.received,
            capture.committed,
            bytes(capture.tail),
            str(capture.path) if capture.path is not None else None,
            "storage_failure",
            False,
            False,
            forced,
        )


async def finalize_output(handle: CommandHandle, forced: bool) -> tuple[OutputResult, OutputResult]:
    """Finalize both transport destinations concurrently without replacing the primary outcome.

    :param handle: Command owning the capture destinations.
    :param forced: Whether transport cleanup was forced.
    :returns: Standard output and standard error results in that order.
    """
    results = await asyncio.gather(
        *(
            seal_capture(handle.captures[name], forced, handle.options.timeouts.finalize)
            for name in ("stdout", "stderr")
        )
    )
    return results[0], results[1]
