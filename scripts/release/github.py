"""GitHub release operations using the existing credential helper, without token output."""

import argparse
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


def request(endpoint: str, payload: dict[str, object] | None = None, *, raw: bool = False) -> Any:
    token = os.environ.get("GH_TOKEN")
    if token is None:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            check=True,
        )
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        token = values["password"]
    query = urllib.request.Request(
        "https://api.github.com/repos/gokurakujoudo/shell-next/" + endpoint,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "shell-next-release",
            "Content-Type": "application/json",
        },
    )
    query.add_unredirected_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(query, timeout=30) as response:
        return response.read() if raw else json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("status", "runs", "jobs", "logs", "draft"))
    parser.add_argument("--run-id")
    parser.add_argument("--job-id")
    arguments = parser.parse_args()
    if arguments.operation == "status":
        result = request("")
        print(
            json.dumps(
                {key: result.get(key) for key in ("full_name", "default_branch", "permissions")}
            )
        )
    elif arguments.operation == "runs":
        result = request("actions/runs?branch=codex%2Fimpl&per_page=5")
        print(
            json.dumps(
                [
                    {
                        key: run[key]
                        for key in ("id", "name", "head_sha", "status", "conclusion", "html_url")
                    }
                    for run in result["workflow_runs"]
                ]
            )
        )
    elif arguments.operation == "jobs":
        result = request(f"actions/runs/{arguments.run_id}/jobs")
        print(
            json.dumps(
                [
                    {
                        "id": job["id"],
                        "name": job["name"],
                        "status": job["status"],
                        "conclusion": job["conclusion"],
                        "failed_steps": [
                            step["name"] for step in job["steps"] if step["conclusion"] == "failure"
                        ],
                    }
                    for job in result["jobs"]
                ]
            )
        )
    elif arguments.operation == "logs":
        content = request(f"actions/jobs/{arguments.job_id}/logs", raw=True)
        Path("reports").mkdir(exist_ok=True)
        destination = Path("reports") / f"github-job-{arguments.job_id}.log"
        destination.write_bytes(content)
        print(destination)
        print(content.decode("utf-8")[-18000:])
    else:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        result = request(
            "releases",
            {
                "tag_name": "v0.1.0a1",
                "target_commitish": sha,
                "name": "shell-next 0.1.0a1 — release candidate",
                "draft": True,
                "prerelease": True,
                "body": "Implementation candidate. Publication remains blocked until all "
                "documented release gates pass. See docs/development/release.md for required "
                "cross-platform, sudo, and coverage evidence.",
            },
        )
        print(json.dumps({key: result[key] for key in ("id", "html_url", "draft", "tag_name")}))


if __name__ == "__main__":
    main()
