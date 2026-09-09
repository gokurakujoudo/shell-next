"""Publish tested distributions to PyPI and attach the same bytes to a GitHub release."""

import hashlib
import json
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from scripts.release.client import request, upload_asset
from scripts.release.verify import main as verify


def pypi_version(version: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/shell-next/{version}/json", timeout=30
        ) as response:
            return dict(json.load(response))
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        return None


def main() -> None:
    verify()
    root = Path.cwd()
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    _, heading, section = changelog.partition(f"## {version}\n")
    if not heading:
        raise SystemExit("The requested version has no changelog section")
    notes = section.split("\n## ", 1)[0].strip()
    directory = root / "dist" / version
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(directory)], check=True)
    files = [
        directory / f"shell_next-{version}-py3-none-any.whl",
        directory / f"shell_next-{version}.tar.gz",
    ]
    subprocess.run(
        [sys.executable, "-m", "twine", "check", *(str(path) for path in files)], check=True
    )
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    existing = pypi_version(version)
    if existing is not None and any(
        hashes.get(item["filename"]) != item["digests"]["sha256"] for item in existing["urls"]
    ):
        raise SystemExit(
            "An existing PyPI version contains different artifacts; refusing replacement"
        )
    releases = request("releases?per_page=100")
    release = next((item for item in releases if item["tag_name"] == f"v{version}"), None)
    if release is None:
        release = request(
            "releases",
            {
                "tag_name": f"v{version}",
                "target_commitish": sha,
                "name": f"shell-next {version}",
                "draft": True,
                "prerelease": False,
                "body": notes
                + f"\n\nTested commit: `{sha}`. "
                + f"Install: `python -m pip install shell-next=={version}`.\n",
            },
        )
    if release["target_commitish"] != sha:
        raise SystemExit("Release target does not match the tested commit")
    for path in files:
        asset = next((item for item in release["assets"] if item["name"] == path.name), None)
        if asset is None:
            upload_asset(release["id"], path)
        elif asset.get("digest") != "sha256:" + hashes[path.name]:
            raise SystemExit("Existing release asset differs; refusing replacement")
    existing_names = set() if existing is None else {item["filename"] for item in existing["urls"]}
    missing = [path for path in files if path.name not in existing_names]
    if missing:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "twine",
                "upload",
                "--non-interactive",
                "--disable-progress-bar",
                *(str(path) for path in missing),
            ],
            check=True,
        )
    published = request(f"releases/{release['id']}", {"draft": False}, method="PATCH")
    print(
        json.dumps(
            {
                "github": published["html_url"],
                "pypi": f"https://pypi.org/project/shell-next/{version}/",
                "commit": sha,
                "sha256": hashes,
            }
        )
    )


if __name__ == "__main__":
    main()
