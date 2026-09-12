"""Opt-in, read-only sudo examples. Windows reports unsupported active elevation."""

import asyncio
import getpass
import sys

from shell_next import (
    Backend,
    CommandOptions,
    PrivilegeRequest,
    ProcessCommand,
    SessionConfig,
    SessionScript,
    use_shell_session,
)


async def password_provider() -> bytes:
    # The terminal belongs to this Python application, not the managed shell.
    password = await asyncio.to_thread(getpass.getpass, "Sudo password: ")
    return password.encode("utf-8")


async def main(backend: Backend, mode: str) -> None:
    if mode not in ("noninteractive", "interactive", "session"):
        raise ValueError("Choose noninteractive, interactive, or session")
    # Collect once before creating the session; applications can pass a secret
    # they already hold directly to SessionConfig(sudo_password=...).
    password = await password_provider() if mode == "session" and backend == Backend.BASH else None
    config = SessionConfig(backend=backend, startup_timeout=30, sudo_password=password)
    async with use_shell_session(config) as shell:
        if not shell.capabilities.privilege_execution:
            print("Active elevation is unsupported; Windows uses the inherited identity.")
            return

        # 1. Noninteractive mode requires policy permission and available credentials.
        # 2. Interactive mode obtains a secret only if sudo asks for one.
        request = PrivilegeRequest(
            requirement="elevated",
            target_identity="root",
            interactive=mode == "interactive",
            password_provider=password_provider if mode == "interactive" else None,
            attempts=1,
        )
        options = CommandOptions(privilege=request)
        command = ProcessCommand("id", ("-u",))
        result = await shell.run(command, options=options, check=True, timeout=30)
        assert result.stdout_str().strip() == "0"
        assert result.privilege.requested and result.privilege.authenticated
        if mode == "session":
            # 3. Reuse the supplied session password for another elevated command.
            # The elevated script still runs in a separate Bash process.
            result = await shell.run(
                SessionScript("demo_elevated=1\nid -u"), options=options, check=True, timeout=30
            )
            assert result.stdout_str().strip() == "0"
            result = await shell.run(
                SessionScript('printf "%s" "${demo_elevated-unset}"'), check=True
            )
            assert result.stdout_str() == "unset"
        print("Read-only identity check succeeded")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python examples/09-sudo.py BACKEND noninteractive|interactive|session"
        )
    asyncio.run(main(Backend(sys.argv[1]), sys.argv[2]))
