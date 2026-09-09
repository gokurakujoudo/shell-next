import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from shell_next import (
    CloseStdin,
    CommandOptions,
    Expect,
    InputPlan,
    Outcome,
    PrivilegeRequest,
    SendLine,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import PrivilegeCleanupError
from tests.support.sessions import config_for, python_command

pytestmark = [
    pytest.mark.integration,
    pytest.mark.sudo,
    pytest.mark.skipif(
        not os.environ.get("SHELL_NEXT_SUDO_PASSWORD"),
        reason="Requires the disposable sudo contract account",
    ),
]


def invalidate_credentials() -> None:
    subprocess.run(["sudo", "-K"], check=True, capture_output=True)


async def test_sudo_authentication_cached_credentials_and_business_input(directory: Path) -> None:
    invalidate_credentials()
    calls = 0

    async def password() -> bytes:
        nonlocal calls
        calls += 1
        return os.environ["SHELL_NEXT_SUDO_PASSWORD"].encode()

    privilege = PrivilegeRequest(
        requirement="elevated", interactive=True, password_provider=password
    )
    command = python_command(
        "import os,sys; print(os.geteuid()); print('business?',flush=True); print(input())"
    )
    plan = InputPlan((Expect(b"business?"), SendLine(b"ordinary input"), CloseStdin()))
    options = CommandOptions(stdin=StdinMode.PLAN, input_plan=plan, privilege=privilege)
    async with use_shell_session(config_for("bash", directory)) as shell:
        first = await shell.run(command, options=options, timeout=15)
        assert first.success and first.privilege.authenticated
        assert first.stdout.tail.startswith(b"0\n")
        assert b"ordinary input" in first.stdout.tail
        assert calls == 1 and first.privilege.attempts == 1
        second = await shell.run(command, options=options, timeout=15)
        assert second.success and calls == 1 and second.privilege.attempts == 0
        assert os.environ["SHELL_NEXT_SUDO_PASSWORD"] not in repr(first)


async def test_wrong_password_and_attempt_limit(directory: Path) -> None:
    invalidate_credentials()
    calls = 0

    async def wrong_password() -> bytes:
        nonlocal calls
        calls += 1
        return b"intentionally-wrong-contract-password"

    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated",
            interactive=True,
            password_provider=wrong_password,
            attempts=1,
        )
    )
    async with use_shell_session(config_for("bash", directory)) as shell:
        result = await shell.run(
            python_command("print('must not run')"), options=options, timeout=15
        )
        assert not result.success and not result.privilege.authenticated
        assert b"must not run" not in result.stdout.tail
        assert calls == 1


async def test_noninteractive_sudo_and_strict_cleanup_rejection(directory: Path) -> None:
    invalidate_credentials()
    options = CommandOptions(privilege=PrivilegeRequest(requirement="elevated"))
    async with use_shell_session(config_for("bash", directory)) as shell:
        result = await shell.run(python_command("print('forbidden')"), options=options, timeout=15)
        assert not result.success and not result.privilege.authenticated
        strict = CommandOptions(
            privilege=PrivilegeRequest(requirement="elevated", strict_cleanup=True)
        )
        with pytest.raises(PrivilegeCleanupError):
            shell.submit(python_command("print('forbidden')"), options=strict)


@pytest.mark.parametrize("provider_fails", [True, False])
async def test_authentication_provider_failure_and_deadline(
    directory: Path,
    provider_fails: bool,
) -> None:
    invalidate_credentials()
    called = asyncio.Event()

    async def provider() -> bytes:
        called.set()
        if provider_fails:
            raise RuntimeError("provider-secret-must-stay-private")
        await asyncio.Event().wait()
        return b"unreachable"

    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated",
            interactive=True,
            password_provider=provider,
        )
    )
    async with use_shell_session(config_for("bash", directory)) as shell:
        result = await shell.run(
            python_command("print('must not run')"), options=options, timeout=3
        )
        assert called.is_set()
        expected = Outcome.STARTUP_FAILURE if provider_fails else Outcome.TIMEOUT
        assert result.outcome == expected and not result.success
        assert b"must not run" not in result.stdout.tail
        assert "provider-secret-must-stay-private" not in repr(result)
        assert not result.cleanup.contained and not shell.is_usable
