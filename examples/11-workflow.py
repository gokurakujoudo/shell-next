"""Compose navigation, environment, scripts, commands, and durable capture."""

import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import (
    Backend,
    CaptureConfig,
    ProcessCommand,
    SessionConfig,
    SessionScript,
    use_shell_session,
)


async def main(backend: Backend) -> None:
    with TemporaryDirectory(prefix="shell-next-workflow-") as directory:
        root = Path(directory)
        project = root / "project"
        logs = root / "logs"
        project.mkdir()
        logs.mkdir()
        (project / "input.txt").write_text("apple\npear\napple\n", encoding="utf-8")
        config = SessionConfig(
            backend=backend,
            cwd=str(root),
            startup_timeout=30,
            capture=CaptureConfig(directory=logs),
        )
        async with use_shell_session(config) as shell:
            await shell.chdir(str(project))
            await shell.set_env("DEMO_FRUIT", "apple")
            script = {
                Backend.BASH: 'test -f input.txt && printf "ready"',
                Backend.POWERSHELL: "if (Test-Path input.txt) { 'ready' } else { throw 'missing' }",
                Backend.CMD: "if exist input.txt (echo ready) else (cmd /c exit 1)",
            }[backend]
            assert (
                await shell.run(SessionScript(script), check=True)
            ).stdout_str().strip() == "ready"

            # Python performs the portable data processing inside the shell's cwd/env.
            source = (
                "import json,os,pathlib; "
                "fruit=os.environ['DEMO_FRUIT']; "
                "lines=pathlib.Path('input.txt').read_text().splitlines(); "
                "print(json.dumps({'fruit': fruit, 'count': lines.count(fruit)}))"
            )
            command = ProcessCommand(sys.executable, ("-c", source))
            result = await shell.run(command, check=True, timeout=10)
            report = json.loads(result.stdout_str())
            assert report == {"fruit": "apple", "count": 2}
            assert result.stdout.path is not None
            captured = await asyncio.to_thread(Path(result.stdout.path).read_bytes)
            assert json.loads(captured) == report
            assert result.stdout.complete and result.stdout.sealed
            assert result.command is command
            print(report)
        # All processes close before the isolated input and capture files disappear.


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
