import os
from pathlib import Path

import pytest

from shell_next import Backend, CommandOptions, PrivilegeRequest, SessionScript, use_shell_session
from shell_next.errors import PrivilegeUnsupportedError
from tests.support.sessions import BACKENDS, config_for, python_command


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_persistent_state_and_structural_inheritance(backend: str, directory: Path) -> None:
    config = config_for(backend, directory)
    async with use_shell_session(config) as shell:
        assert await shell.ping()
        subdirectory = directory / "space and 中文"
        subdirectory.mkdir()
        await shell.chdir(str(subdirectory))
        assert Path(await shell.get_cwd()) == subdirectory
        await shell.set_env("SHELL_NEXT_TEST", "stateful & literal")
        assert await shell.get_env("SHELL_NEXT_TEST") == "stateful & literal"
        native = {
            "bash": "local_value=42; function saved_function() { printf '%s' \"$local_value\"; }; "
            "export SHELL_NEXT_NATIVE=kept",
            "powershell": "$local_value=42; function saved_function { $local_value }; "
            "$env:SHELL_NEXT_NATIVE='kept'",
            "cmd": "set local_value=42\nset SHELL_NEXT_NATIVE=kept",
        }[backend]
        assert (await shell.run(SessionScript(native), timeout=10)).success
        read = "echo %local_value%" if backend == "cmd" else "saved_function"
        assert (await shell.run(SessionScript(read), timeout=10)).stdout.tail.strip() == b"42"
        result = await shell.run(
            python_command("import os; print(os.environ['SHELL_NEXT_NATIVE'])"), timeout=10
        )
        assert result.stdout.tail.strip() == b"kept"
        await shell.unset_env("SHELL_NEXT_TEST")
        assert await shell.get_env("SHELL_NEXT_TEST") is None
        assert isinstance(await shell.get_env(), dict)
        assert "SHELL_NEXT_NATIVE" not in os.environ


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt", reason="Windows elevation policy")
@pytest.mark.parametrize("backend", ["powershell", "cmd"])
async def test_windows_rejects_elevation(backend: str, directory: Path) -> None:
    async with use_shell_session(config_for(backend, directory)) as shell:
        with pytest.raises(PrivilegeUnsupportedError):
            shell.submit(
                SessionScript("echo forbidden"),
                options=CommandOptions(privilege=PrivilegeRequest(requirement="elevated")),
            )


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt", reason="PowerShell error semantics")
@pytest.mark.parametrize(
    "script,terminating", [("Write-Error 'failure'", False), ("throw 'failure'", True)]
)
async def test_powershell_error_dimensions(script: str, terminating: bool, directory: Path) -> None:
    async with use_shell_session(config_for(Backend.POWERSHELL, directory)) as shell:
        result = await shell.run(SessionScript(script), timeout=10)
        assert not result.success
        assert result.status.last_success is False
        assert result.status.terminating_error is terminating
        assert b"failure" in result.stderr.tail
