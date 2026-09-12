"""Inspect and change the shell directory without changing Python's directory."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    parent_cwd = Path.cwd()
    with TemporaryDirectory(prefix="shell-next-navigation-") as directory:
        root = await asyncio.to_thread(Path(directory).resolve)
        child = root / "project with spaces"
        child.mkdir()
        config = SessionConfig(backend=backend, cwd=str(root), startup_timeout=30)
        async with use_shell_session(config) as shell:
            # 1. Inspect the initial directory and the cached snapshot.
            assert Path(await shell.get_cwd()) == root
            assert shell.snapshot().cwd == str(root)

            # 2. Navigate relatively, then let a child process inherit the cwd.
            await shell.chdir("project with spaces")
            assert Path(await shell.get_cwd()) == child
            command = ProcessCommand(sys.executable, ("-c", "import os; print(os.getcwd())"))
            result = await shell.run(command, check=True)
            assert Path(result.stdout_str().strip()) == child
            await shell.chdir("..")
            assert Path(await shell.get_cwd()) == root
            assert Path.cwd() == parent_cwd
            print("Only the shell moved; Python stayed in", parent_cwd)
        # Close the shell before removing directories it may still have open.


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
