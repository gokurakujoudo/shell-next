import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from shell_next.backends.native import bridge


@pytest.mark.parametrize(
    "elevated,interactive,authenticated",
    [
        (False, False, False),
        (True, False, False),
        (True, False, True),
        (True, True, True),
        (True, True, False),
    ],
)
def test_structural_bridge_privilege_phases(
    elevated: bool,
    interactive: bool,
    authenticated: bool,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = {
        name: str(directory / name) for name in ("stdin", "stdout", "stderr", "auth_in", "auth_out")
    }
    Path(paths["stdin"]).write_bytes(b"business")
    Path(paths["auth_in"]).write_bytes(b"private\n")
    manifest = directory / "command.json"
    manifest.write_text(
        json.dumps(
            {
                **paths,
                "argv": ["program", "a & b"],
                "token": "token",
                "elevated": elevated,
                "interactive": interactive,
                "target": "root",
                "attempts": 1,
            }
        )
    )
    calls: list[list[str]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        assert kwargs["stdin"].read() == b"business"
        kwargs["stdout"].write(b"result")
        return subprocess.CompletedProcess(argv, 0)

    def authenticate(*args: object) -> tuple[bool, int]:
        return authenticated, int(interactive)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(bridge, "authenticate", authenticate)
    code = bridge.main(str(manifest))
    assert code == (126 if elevated and not authenticated else 0)
    if elevated and not authenticated:
        assert not calls
    else:
        assert calls[0][-2:] == ["program", "a & b"]
        assert Path(paths["stdout"]).read_bytes() == b"result"
    assert "private" not in capsys.readouterr().out


def test_bridge_startup_failure_and_script_entry(
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = {name: str(directory / name) for name in ("stdin", "stdout", "stderr")}
    Path(paths["stdin"]).write_bytes(b"")
    manifest = directory / "command.json"
    manifest.write_text(json.dumps({**paths, "argv": ["missing"], "token": "token"}))

    def fail(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(sys, "argv", [str(bridge.__file__), str(manifest)])
    with pytest.raises(SystemExit) as failure:
        runpy.run_path(str(bridge.__file__), run_name="__main__")
    assert failure.value.code == 127
    assert b"could not start" in Path(paths["stderr"]).read_bytes()
