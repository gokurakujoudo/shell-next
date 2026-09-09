"""Fail closed unless the exact publishing commit has complete release evidence."""

import json
import os
import subprocess
import tomllib
from pathlib import Path

from scripts.release.github import request


def main() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    if os.environ["VERSION"] != project["version"]:
        raise SystemExit("Requested version does not match package metadata")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    evidence = json.loads(
        Path("docs/development/release-evidence.json").read_text(encoding="utf-8")
    )
    if evidence.get("commit") != sha or not all(
        evidence.get(name) is True
        for name in (
            "rhel8_reference",
            "interactive_sudo",
            "windows_contracts",
            "leak_checks",
            "coverage_100",
            "installed_wheel",
        )
    ):
        raise SystemExit("Exact-commit release evidence is incomplete")
    runs = request(f"actions/workflows/ci.yml/runs?head_sha={sha}")["workflow_runs"]
    if not any(run["head_sha"] == sha and run["conclusion"] == "success" for run in runs):
        raise SystemExit("Quality workflow has not passed for this exact commit")


if __name__ == "__main__":
    main()
