import asyncio
from typing import Any, cast

import pytest

from shell_next import Backend, SessionConfig, TimeoutPolicy
from shell_next.backends.native.driver import NativeDriver
from shell_next.backends.native.termination import stop_native
from shell_next.models.results import CleanupReport


@pytest.mark.parametrize("mode", ["timeout", "signal_error", "already_closed"])
async def test_soft_stop_failures_still_force_cleanup(mode: str) -> None:
    calls: list[str] = []

    class Containment:
        def terminate(self, force: bool = True) -> None:
            calls.append("soft")
            assert not force
            if mode == "signal_error":
                raise OSError("signal failed")

    class Process:
        async def wait(self) -> int:
            await asyncio.Event().wait()
            return 0

    class Native:
        containment = Containment()
        process = None if mode == "already_closed" else Process()

        async def close(self, wait_timeout: float | None = None) -> CleanupReport:
            calls.append("force")
            return CleanupReport(forced=True)

    driver = NativeDriver(SessionConfig(Backend.BASH))
    driver.native = cast(Any, Native())
    driver.timeouts = TimeoutPolicy(soft_stop=0)
    result = await stop_native(driver)
    assert result.soft_stop and result.forced
    assert calls == ["soft", "force"]
    assert result.errors == (("OSError",) if mode == "signal_error" else ())
