"""Persistent cmd batch wrappers and conservative control-path validation."""

from shell_next.errors import ConfigurationError


def quote(value: str) -> str:
    """Quote a trusted batch-control path without expansion or command injection.

    :param value: Literal path.
    :returns: Double-quoted batch word.
    :raises ConfigurationError: Batch expansion makes this path unsafe.
    """
    if any(character in value for character in '\r\n"%!'):
        raise ConfigurationError("cmd control paths cannot contain quotes, %, !, CR or LF")
    return '"' + value + '"'


def wrapper(text: str, token: str, script: bool, channels: dict[str, str]) -> str:
    """Call a batch file in persistent state and preserve its ERRORLEVEL.

    :param text: Private batch or bridge invocation.
    :param token: Reserved status marker; the caller reports it after this wrapper returns.
    :param script: Whether native stream redirection is required.
    :param channels: Command-specific named pipe endpoints.
    :returns: Native batch wrapper.
    """
    if script:
        text += " " + " ".join(
            f"{fd}{direction}{quote(channels[name])}"
            for fd, direction, name in ((0, "<", "stdin"), (1, ">", "stdout"), (2, ">", "stderr"))
        )
    return f"@echo off\n{text}\n"
