"""Inspect failures, time out an observation, and explicitly stop an owned command."""

import asyncio
import os
import sys

from shell_next import (
    Backend,
    CommandOptions,
    Outcome,
    ProcessCommand,
    SessionConfig,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import CommandFailedError


async def main(backend: Backend) -> None:
    config = SessionConfig(backend=backend, startup_timeout=30)
    async with use_shell_session(config) as shell:
        # 1. A nonzero exit is a normal EXITED outcome with success=False.
        failure = ProcessCommand(sys.executable, ("-c", "import sys; sys.exit(7)"))
        result = await shell.run(failure)
        assert result.outcome == Outcome.EXITED and not result.success
        assert result.status.code == 7
        try:
            await shell.run(failure, check=True)
        except CommandFailedError as error:
            assert error.result.command is failure
            assert error.result.status.code == 7
        else:
            raise AssertionError("check=True must report failure")

        # 2. This process waits for EOF; timing out observation does not stop it.
        command = ProcessCommand(
            sys.executable,
            ("-u", "-c", "import sys; print('ready', flush=True); sys.stdin.read(); print('done')"),
        )
        options = CommandOptions(stdin=StdinMode.MANUAL)
        async with shell.command(command, options=options, timeout=10) as handle:
            await handle.expect(b"ready", timeout=5)
            try:
                await handle.wait(wait_timeout=0)
            except TimeoutError:
                pass
            else:
                raise AssertionError("The process is still waiting for EOF")
            await handle.close_stdin()
            assert (await handle.wait()).success
        await shell.ping()
        assert shell.is_usable

        # 3. A deliberate stop finalizes cleanup; do not assume session reuse.
        async with shell.command(command, options=options, timeout=10) as handle:
            await handle.expect(b"ready", timeout=5)
            result = await handle.stop()
        assert result.outcome == Outcome.STOPPED
        print("Reusable:", result.session_reusable, "Cleanup:", result.cleanup)
        # No more commands are submitted; the outer scope closes this session.


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
