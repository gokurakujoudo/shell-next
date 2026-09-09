"""Fail closed unless the exact publishing commit has complete release evidence."""

import os
import subprocess
import tomllib
from pathlib import Path

from scripts.release.client import request


def main() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    if os.environ.get("VERSION", project["version"]) != project["version"]:
        raise SystemExit("Requested version does not match package metadata")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise SystemExit("Release builds require a clean tested checkout")
    runs = request(f"actions/workflows/ci.yml/runs?head_sha={sha}")["workflow_runs"]
    successful = [run for run in runs if run["head_sha"] == sha and run["conclusion"] == "success"]
    if not successful:
        raise SystemExit("Quality workflow has not passed for this exact commit")
    jobs = request(f"actions/runs/{successful[0]['id']}/jobs")["jobs"]
    passed = {job["name"] for job in jobs if job["conclusion"] == "success"}
    required = {
        "contracts (ubuntu-latest)",
        "contracts (windows-latest)",
        "rhel8-reference",
        "release-gates",
    }
    if not required <= passed:
        raise SystemExit("The complete release matrix has not passed")


if __name__ == "__main__":
    main()
