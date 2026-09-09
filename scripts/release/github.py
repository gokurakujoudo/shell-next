"""GitHub release operations using the existing credential helper, without token output."""

import argparse
import io
import json
import zipfile
from pathlib import Path

from scripts.release.client import request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("status", "runs", "jobs", "logs", "coverage"))
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
        result = request("actions/runs?per_page=5")
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
        print(content.decode("utf-8-sig")[-18000:].encode("ascii", "backslashreplace").decode())
    elif arguments.operation == "coverage":
        artifacts = request(f"actions/runs/{arguments.run_id}/artifacts")["artifacts"]
        for artifact in artifacts:
            if artifact["name"].startswith("coverage-"):
                data = request(f"actions/artifacts/{artifact['id']}/zip", raw=True)
                destination = Path("reports") / "coverage" / artifact["name"]
                destination.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    (destination / ".coverage").write_bytes(archive.read(".coverage"))
                print(destination)


if __name__ == "__main__":
    main()
