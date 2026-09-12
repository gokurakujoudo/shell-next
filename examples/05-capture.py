"""Decode separate streams, bound memory, and preserve complete output in files."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import Backend, CaptureConfig, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    command = ProcessCommand(
        sys.executable,
        ("-c", "import sys; sys.stdout.write('prefix:done'); sys.stderr.write('warning')"),
    )
    # 1. The default retains up to 64 KiB independently for each stream.
    async with use_shell_session(SessionConfig(backend=backend, startup_timeout=30)) as shell:
        result = await shell.run(command, check=True)
        assert result.stdout_str() == "prefix:done"
        assert result.stderr_str() == "warning"
        assert result.stdout.tail == b"prefix:done"

    # 2. A four-byte tail still drains and counts the entire output.
    config = SessionConfig(backend=backend, capture=CaptureConfig(tail_bytes=4), startup_timeout=30)
    async with use_shell_session(config) as shell:
        result = await shell.run(command, check=True)
        assert result.stdout_str() == "done"
        assert result.stderr_str() == "ning"
        assert result.stdout.received == 11
        assert not result.stdout.complete

    # 3. Persist all bytes while keeping the same bounded memory tail.
    with TemporaryDirectory(prefix="shell-next-capture-") as directory:
        config = SessionConfig(
            backend=backend,
            startup_timeout=30,
            capture=CaptureConfig(tail_bytes=4, directory=Path(directory)),
        )
        async with use_shell_session(config) as shell:
            result = await shell.run(command, check=True)
            assert result.stdout.path is not None
            assert await asyncio.to_thread(Path(result.stdout.path).read_bytes) == b"prefix:done"
            assert result.stdout.tail == b"done"
            assert result.stdout.committed == result.stdout.received == 11
            assert result.stdout.complete and result.stdout.sealed
            assert not result.stdout.unread_possible
            print("Full capture verified; temporary files are removed on exit")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
