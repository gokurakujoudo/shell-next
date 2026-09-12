import os
from pathlib import Path

import pytest

from shell_next import SessionScript, use_shell_session
from tests.support.sessions import config_for


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt", reason="cmd batch-file lifecycle requires Windows")
async def test_repeated_cmd_scripts_survive_immediate_command_cleanup(directory: Path) -> None:
    async with use_shell_session(config_for("cmd", directory)) as shell:
        for index in range(128):
            result = await shell.run(SessionScript(f"echo command-{index}"), timeout=5)
            assert result.success, (index, result.outcome, result.secondary_errors)
            assert result.stdout_str().strip() == f"command-{index}"
            assert result.session_reusable and shell.is_usable
