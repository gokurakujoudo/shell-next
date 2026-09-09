"""Repository-scoped GitHub requests using existing credentials without logging them."""

import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = "gokurakujoudo/shell-next"


def credential() -> str:
    token = os.environ.get("GH_TOKEN")
    if token is not None:
        return token
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return values["password"]


def request(
    endpoint: str,
    payload: dict[str, object] | None = None,
    *,
    raw: bool = False,
    method: str | None = None,
) -> Any:
    query = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/" + endpoint,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "shell-next-release",
            "Content-Type": "application/json",
        },
        method=method,
    )
    query.add_unredirected_header("Authorization", "Bearer " + credential())
    with urllib.request.urlopen(query, timeout=30) as response:
        return response.read() if raw else json.load(response)


def upload_asset(release_id: int, path: Path) -> Any:
    query = urllib.request.Request(
        f"https://uploads.github.com/repos/{REPOSITORY}/releases/{release_id}/assets?"
        + urllib.parse.urlencode({"name": path.name}),
        data=path.read_bytes(),
        headers={"Content-Type": "application/octet-stream", "User-Agent": "shell-next-release"},
    )
    query.add_unredirected_header("Authorization", "Bearer " + credential())
    with urllib.request.urlopen(query, timeout=60) as response:
        return json.load(response)
