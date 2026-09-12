import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.tutorials import tutorial_examples


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["bash", "powershell", "cmd"])
@pytest.mark.parametrize(
    "filename,source",
    tutorial_examples("native"),
    ids=[name for name, _ in tutorial_examples("native")],
)
def test_native_tutorial_source(backend: str, filename: str, source: str, directory: Path) -> None:
    if (backend == "bash") == (os.name == "nt"):
        pytest.skip(f"{backend} tutorial requires its supported native operating system")
    result = subprocess.run(
        [sys.executable, "-c", source, backend],
        cwd=directory,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, (filename, backend, result.stdout, result.stderr)
