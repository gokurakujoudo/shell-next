import sys
from pathlib import Path

import pytest

from shell_next import CommandOptions, Outcome, SessionScript, TimeoutPolicy, use_shell_session
from tests.support.sessions import BACKENDS, config_for, python_command


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_explicit_shell_exit_invalidates_protocol(backend: str, directory: Path) -> None:
    script = "[Environment]::Exit(3)" if backend == "powershell" else "exit 3"
    async with use_shell_session(config_for(backend, directory)) as shell:
        result = await shell.run(SessionScript(script), timeout=10)
        assert result.outcome == Outcome.SESSION_LOST
        assert not shell.is_usable and not result.session_reusable


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_background_descendant_cannot_hold_capture_open_forever(
    backend: str, directory: Path
) -> None:
    command = python_command(
        "import subprocess,sys; subprocess.Popen([sys.executable,'-c',"
        "'import time; time.sleep(60)']); print('parent exited')"
    )
    async with use_shell_session(config_for(backend, directory)) as shell:
        options = CommandOptions(timeouts=TimeoutPolicy(execution=10, drain=0.1))
        result = await shell.run(command, options=options)
        assert result.outcome == Outcome.OUTPUT_FAILURE
        assert result.status.code == 0
        assert result.cleanup.forced and not result.stdout.complete
        assert b"parent exited" in result.stdout.tail
        assert not shell.is_usable


@pytest.mark.integration
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX cooperative termination")
async def test_ignored_soft_termination_escalates_to_force(directory: Path) -> None:
    command = python_command(
        "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "print('ready',flush=True); time.sleep(60)"
    )
    async with use_shell_session(config_for("bash", directory)) as shell:
        options = CommandOptions(timeouts=TimeoutPolicy(soft_stop=0.01))
        async with shell.command(command, options=options, timeout=10) as handle:
            await handle.expect(b"ready")
            result = await handle.stop()
            assert result.cleanup.soft_stop and result.cleanup.forced
