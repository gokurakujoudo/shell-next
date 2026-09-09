from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def directory() -> Iterator[Path]:
    with TemporaryDirectory(prefix="shell-next-test-") as path:
        yield Path(path)
