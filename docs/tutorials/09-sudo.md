# Sudo and backend capabilities

Bash on Linux supports active sudo elevation. PowerShell and cmd on Windows
can use their inherited process identity but cannot request active elevation.
The example checks `shell.capabilities.privilege_execution` before submission.

Run one mode explicitly on a Linux account whose sudo policy permits `id -u`.
The `session` mode also runs an elevated Bash script, so its account must already
have permission for that Bash invocation. An `id`-only policy is sufficient for
the `noninteractive` and `interactive` modes, but not the complete `session` demo:

```console
python examples/09-sudo.py bash noninteractive
python examples/09-sudo.py bash interactive
python examples/09-sudo.py bash session
```

1. `noninteractive` requests root with no password prompt. It needs a permitted
   passwordless policy or credentials already available to sudo. Authentication
   failure is reported; there is no automatic interactive fallback.
2. `interactive` supplies an async password provider. It calls `getpass` from
   this Python application's terminal in a worker thread, only if sudo asks.
   A credential cache hit needs no provider call. Never hardcode a real password
   or send it through business stdin. Private authentication channels keep it
   out of command argv, results, and mock call history.
3. `session` collects the password once before session creation and passes it to
   `SessionConfig(sudo_password=...)`. An application can pass an already-held
   string or bytes value directly without prompting. Both an elevated process
   and a later elevated script use it only when sudo requests authentication.
   The script runs in a separate elevated Bash process; a later ordinary script
   proves its assignment did not persist. `target_identity` selects the target.

The session password requires shell-next 0.1.3+. It does not elevate ordinary
commands. An explicit per-command provider overrides the session password.
A password with `None` means no fallback; empty text/bytes are an empty password.
The configuration retains the secret in memory but omits it from repr, equality,
and `to_dict()`. Closing the session does not erase caller-owned configuration.

Run `python examples/09-sudo.py powershell noninteractive` (or `cmd`) on Windows
to see the capability explanation without requesting elevation. Sudo is not
installed or configured by this example. Authentication failures raise a typed
privilege error; provider failures expose a generic authentication diagnostic.
Privileged descendants cannot be guaranteed contained after changing identity;
`strict_cleanup=True` is rejected. The examples do not alter sudo policy.

The documentation check executes this exact code with injected mock scenarios
for all three modes, including a password request and a cache hit. Native sudo
behavior is covered separately by the configured Linux sudo contract tests;
a mocked tutorial run is not evidence of live sudo policy on your machine.

## Full example

File: [`examples/09-sudo.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/09-sudo.py).

<!-- python-doc-exec sudo: 09-sudo.py -->
```python
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
```

[Tutorial contents](index.md)
