"""Run native syntax, preserve shell variables, and execute a trusted script file."""

import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from shell_next import Backend, SessionConfig, SessionScript, use_shell_session


async def main(backend: Backend) -> None:
    # The three entries are native programs with the same observable intent.
    assign, read, pipeline, suffix = {
        Backend.BASH: (
            "demo_answer=42",
            'printf "%s\\n" "$demo_answer"',
            "printf 'apple\\npear\\n' | grep apple",
            ".sh",
        ),
        Backend.POWERSHELL: (
            "$demo_answer = 42",
            "Write-Output $demo_answer",
            "'apple', 'pear' | Where-Object { $_ -eq 'apple' }",
            ".ps1",
        ),
        Backend.CMD: (
            'set "demo_answer=42"',
            "echo %demo_answer%",
            "(echo apple&echo pear) | findstr apple",
            ".cmd",
        ),
    }[backend]
    with TemporaryDirectory(prefix="shell-next-script-") as directory:
        config = SessionConfig(backend=backend, cwd=directory, startup_timeout=30)
        async with use_shell_session(config) as shell:
            # 1. Operators and shell built-ins belong in SessionScript.
            result = await shell.run(SessionScript(pipeline), check=True)
            assert result.stdout_str().strip() == "apple"

            # 2. A variable assigned in one call survives into the next call.
            await shell.run(SessionScript(assign), check=True)
            result = await shell.run(SessionScript(read), check=True)
            assert result.stdout_str().strip() == "42"

            # 3. Load a trusted file as native source in the existing session.
            path = Path(directory) / ("demo" + suffix)
            path.write_text(assign + "\n" + read + "\n", encoding="utf-8")
            result = await shell.run(SessionScript(path.read_text(encoding="utf-8")), check=True)
            assert result.stdout_str().strip() == "42"
            print(result.stdout_str(), end="")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
