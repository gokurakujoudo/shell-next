"""Portable state operations expressed in each backend's native language."""

import json
import re
import sys
from typing import TYPE_CHECKING

from shell_next.backends.native.syntax import quote
from shell_next.errors import ConfigurationError, SessionProtocolError
from shell_next.models.commands import ProcessCommand, SessionScript
from shell_next.models.state import Backend

if TYPE_CHECKING:
    from shell_next.frontend.session import ShellSession


async def state_operation(
    session: ShellSession, operation: str, name: str | None = None, value: str | None = None
) -> str | dict[str, str] | None:
    """Run an explicit portable state operation and update the cached snapshot.

    :param session: Active session.
    :param operation: Directory or exported-environment operation name.
    :param name: Path or variable name, when required.
    :param value: Exported value for set_env.
    :returns: Observed state, or None after a mutation.
    :raises ConfigurationError: The supplied variable name or value is invalid.
    :raises SessionProtocolError: A state query exceeded capture bounds.
    """
    backend = session.config.backend
    if operation in ("get_cwd", "get_env"):
        code = (
            "import os,json; print(json.dumps(os.getcwd()))"
            if operation == "get_cwd"
            else "import os,json; print(json.dumps(dict(os.environ)))"
        )
        result = await session.run(ProcessCommand(sys.executable, ("-c", code)), check=True)
        if not result.stdout.complete:
            raise SessionProtocolError("State query exceeded configured capture bounds")
        observed = json.loads(result.stdout.tail)
        if operation == "get_cwd":
            session.cwd = str(observed)
            return session.cwd
        session.environment = {str(k): str(v) for k, v in observed.items()}
        return session.environment.get(name) if name is not None else dict(session.environment)
    assert name is not None
    if operation == "chdir":
        text = {
            Backend.BASH: "cd -- ",
            Backend.POWERSHELL: "Set-Location -LiteralPath ",
            Backend.CMD: "cd /d ",
        }[backend] + quote(name, backend)
    else:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
            raise ConfigurationError("Portable environment names must be shell identifiers")
        if value is not None and "\0" in value:
            raise ConfigurationError("Environment values cannot contain NUL")
        if operation == "unset_env":
            text = {
                Backend.BASH: f"unset {name}",
                Backend.POWERSHELL: f"Remove-Item Env:{name} -ErrorAction SilentlyContinue",
                Backend.CMD: f'set "{name}="',
            }[backend]
        elif backend == Backend.BASH:
            text = f"export {name}={quote(value or '', backend)}"
        elif backend == Backend.POWERSHELL:
            text = f"[Environment]::SetEnvironmentVariable('{name}', {quote(value or '', backend)})"
        else:
            text = "set " + quote(f"{name}={value or ''}", backend)
    await session.run(SessionScript(text), check=True)
    session.record(operation, name)
    if operation == "chdir":
        session.cwd = name
    elif operation == "unset_env":
        session.environment.pop(name, None)
    else:
        session.environment[name] = value or ""
    return None
