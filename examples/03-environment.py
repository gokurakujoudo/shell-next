"""Configure, update, inspect, and remove an exported session variable."""

import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    parent_value = os.environ.get("SHELL_NEXT_DEMO_MODE")
    config = SessionConfig(
        backend=backend, env={"SHELL_NEXT_DEMO_MODE": "preview"}, startup_timeout=30
    )
    async with use_shell_session(config) as shell:
        # 1. Initial overrides belong to this session, not the Python parent.
        assert await shell.get_env("SHELL_NEXT_DEMO_MODE") == "preview"
        assert os.environ.get("SHELL_NEXT_DEMO_MODE") == parent_value

        # 2. A later process inherits updates made through the portable helper.
        await shell.set_env("SHELL_NEXT_DEMO_MODE", "release candidate")
        command = ProcessCommand(
            sys.executable, ("-c", "import os; print(os.environ['SHELL_NEXT_DEMO_MODE'])")
        )
        result = await shell.run(command, check=True)
        assert result.stdout_str().strip() == "release candidate"
        environment = await shell.get_env()
        assert isinstance(environment, dict)
        assert environment["SHELL_NEXT_DEMO_MODE"] == "release candidate"
        assert dict(shell.snapshot().environment)["SHELL_NEXT_DEMO_MODE"] == "release candidate"

        # 3. Remove the variable explicitly; None means it is absent.
        await shell.unset_env("SHELL_NEXT_DEMO_MODE")
        assert await shell.get_env("SHELL_NEXT_DEMO_MODE") is None
        assert os.environ.get("SHELL_NEXT_DEMO_MODE") == parent_value
        print("Session environment updated and removed")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
