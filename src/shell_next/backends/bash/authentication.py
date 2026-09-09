"""Dedicated sudo authentication in the business bridge's parent identity scope."""

import subprocess
from typing import BinaryIO


def authenticate(
    target: str | None,
    attempts: int,
    prompt: bytes,
    requests: BinaryIO | None,
    responses: BinaryIO | None,
) -> tuple[bool, int]:
    """Authenticate sudo without ever sharing the business stdin transport.

    Authentication and business sudo invocations must have the same parent
    bridge so sudo's non-terminal parent-process timestamp scope remains valid.

    :param target: Optional sudo target user.
    :param attempts: Maximum password submissions.
    :param prompt: Unique private ASCII password prompt.
    :param requests: Separate password-request pipe, or None for noninteractive sudo.
    :param responses: Separate secret response pipe, or None for noninteractive sudo.
    :returns: Authentication success and password-submission count.
    """
    argv = ["sudo", *(["-u", target] if target is not None else [])]
    if requests is None or responses is None:
        code = subprocess.run(
            [*argv, "-n", "-v"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        return code == 0, 0
    used = 0
    with subprocess.Popen(
        [*argv, "-S", "-p", prompt.decode("ascii"), "-v"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    ) as process:
        assert process.stdin is not None and process.stderr is not None
        window = bytearray()
        while data := process.stderr.read(1):
            window.extend(data)
            del window[: -len(prompt)]
            if bytes(window) != prompt:
                continue
            if used >= attempts:
                process.stdin.close()
                break
            requests.write(b"password\n")
            requests.flush()
            password = responses.readline(65536)
            if not password.endswith(b"\n"):
                process.stdin.close()
                break
            process.stdin.write(password)
            process.stdin.flush()
            del password
            used += 1
            window.clear()
        process.stdin.close()
        return process.wait() == 0, used
