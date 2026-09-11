import re
import subprocess
import sys
from pathlib import Path

from scripts.docs.validate import validate


def test_marked_documentation_examples(directory: Path) -> None:
    documents = [Path("README.md"), *Path("docs").rglob("*.md")]
    examples = [
        (path, source)
        for path in documents
        for source in re.findall(
            r"<!-- python-doc-exec -->\s*```python\n(.*?)\n```",
            path.read_text(encoding="utf-8"),
            re.DOTALL,
        )
    ]
    assert examples, "No executable documentation examples discovered"
    for path, source in examples:
        completed = subprocess.run(
            [sys.executable, "-c", source],
            cwd=directory,
            capture_output=True,
            timeout=30,
        )
        assert completed.returncode == 0, (path, completed.stdout, completed.stderr)


def test_rendered_site_validator_checks_relative_and_project_root_links(directory: Path) -> None:
    (directory / "guide").mkdir()
    (directory / "index.html").write_text(
        '<a href="guide/#topic">Guide</a><img src="logo.png">', encoding="utf-8"
    )
    (directory / "guide/index.html").write_text(
        '<h1 id="topic">Topic</h1><a href="/shell-next/">Home</a>', encoding="utf-8"
    )
    (directory / "logo.png").write_bytes(b"asset")
    assert validate(directory) == []
    (directory / "index.html").write_text(
        '<a href="guide/#missing">Missing anchor</a><img src="missing.png">'
        '<a href="/other/">Outside project</a>',
        encoding="utf-8",
    )
    errors = validate(directory)
    assert len(errors) == 3
    assert any("missing fragment" in error for error in errors)
    assert any("missing.png" in error for error in errors)
    assert any("outside site" in error for error in errors)
