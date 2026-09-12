"""Run one command, preserve arguments, then run an ordered sequence."""

import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    config = SessionConfig(backend=backend, startup_timeout=30)
    async with use_shell_session(config) as shell:
        # 1. Run an ordinary external command through the selected shell.
        result = await shell.run(ProcessCommand(sys.executable, ("--version",)), check=True)
        assert "Python 3." in result.stdout_str()
        print(result.stdout_str(), end="")

        # 2. Arguments remain literal, including spaces and shell operators.
        value = "two words & literal | text"
        command = ProcessCommand(sys.executable, ("-c", "import sys; print(sys.argv[1])", value))
        result = await shell.run(command, check=True)
        assert result.stdout_str().strip() == value
        assert result.command is command

        # 3. Await each command to preserve order and stop on the first failure.
        outputs = []
        for number in (1, 2, 3):
            command = ProcessCommand(sys.executable, ("-c", f"print({number})"))
            result = await shell.run(command, check=True, timeout=10)
            outputs.append(result.stdout_str().strip())
        assert outputs == ["1", "2", "3"]
        print(outputs)


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
