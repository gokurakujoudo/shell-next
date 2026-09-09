import os
import sys
from pathlib import Path

from shell_next import (
    Backend,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
)

BACKENDS = ["mock", *(["cmd", "powershell"] if os.name == "nt" else ["bash"])]


def python_command(code: str, *args: str) -> ProcessCommand:
    return ProcessCommand(sys.executable, ("-u", "-c", code, *args))


def config_for(backend: str, directory: Path, *expectations: MockExpectation) -> SessionConfig:
    config = SessionConfig(
        Backend.BASH if backend == "mock" else Backend(backend), cwd=str(directory)
    )
    if backend == "mock":
        config._session_cls = MockShellSession.configured(MockScenario(list(expectations)))
    return config
