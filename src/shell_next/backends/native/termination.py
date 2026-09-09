"""Bounded native soft-stop and forced-containment cleanup."""

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from shell_next.models.results import CleanupReport
from shell_next.models.state import Backend

if TYPE_CHECKING:
    from shell_next.backends.native.driver import NativeDriver


async def stop_native(driver: NativeDriver) -> CleanupReport:
    """Attempt a cooperative Bash stop, then clean the complete containment unit.

    :param driver: Native driver owning the interpreter and output pumps.
    :returns: Cleanup evidence including any unsuccessful soft-stop attempt.
    """
    native = driver.native
    soft = False
    errors: list[str] = []
    if driver.config.backend == Backend.BASH and native.containment is not None:
        soft = True
        try:
            native.containment.terminate(force=False)
            if native.process is not None:
                await asyncio.wait_for(native.process.wait(), driver.timeouts.soft_stop)
        except TimeoutError:
            pass
        except OSError as exc:
            errors.append(type(exc).__name__)
    report = await native.close(driver.timeouts.force_stop)
    try:
        async with asyncio.timeout(driver.timeouts.drain):
            results = await asyncio.gather(*driver.pumps, return_exceptions=True)
            errors.extend(
                type(result).__name__ for result in results if isinstance(result, Exception)
            )
    except (TimeoutError, OSError) as exc:
        errors.append(type(exc).__name__)
    return replace(report, soft_stop=soft, errors=(*report.errors, *errors))
