"""Persistent Bash command wrappers with separate private control output."""

import shlex


def quote(value: str) -> str:
    """Represent one literal Bash word using standard POSIX quoting.

    :param value: Literal value.
    :returns: Quoted native shell word.
    """
    return shlex.quote(value)


def wrapper(text: str, token: str, script: bool, channels: dict[str, str]) -> str:
    """Execute in current Bash scope and report status on reserved descriptor 9.

    :param text: Trusted private script or bridge invocation.
    :param token: Random command control marker.
    :param script: Whether business stream redirection is required.
    :param channels: stdin, stdout, and stderr FIFO paths.
    :returns: Native wrapper text.
    """
    if script:
        redirect = " ".join(
            f"{fd}{direction}{quote(channels[name])}"
            for fd, direction, name in ((0, "<", "stdin"), (1, ">", "stdout"), (2, ">", "stderr"))
        )
        text = f"{{ printf '{token}:ready\\n' >&9; {text}; }} {redirect}"
    return f"{text}\nsn_status=$?\nprintf '{token}:%s\\n' \"$sn_status\" >&9\n"
