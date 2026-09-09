import sys
from pathlib import Path

import pytest

from shell_next import CommandOptions, SessionScript, StdinMode, use_shell_session
from shell_next.backends.native.syntax import invocation
from shell_next.models.state import Backend
from tests.support.sessions import BACKENDS, config_for


@pytest.mark.integration
@pytest.mark.parametrize("backend", [name for name in BACKENDS if name != "mock"])
async def test_native_script_process_reads_business_input(backend: str, directory: Path) -> None:
    program = directory / "read-input.py"
    program.write_text("print(input())\n", encoding="utf-8")
    script = SessionScript(invocation([sys.executable, str(program)], Backend(backend)))
    async with use_shell_session(config_for(backend, directory)) as shell:
        async with shell.command(
            script, options=CommandOptions(stdin=StdinMode.MANUAL), timeout=10
        ) as handle:
            await handle.sendline(b"script-business-input")
            result = await handle.wait()
            assert result.success
            assert result.stdout.tail.strip() == b"script-business-input"
