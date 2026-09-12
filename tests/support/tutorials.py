import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "docs/tutorials"
PATTERN = r"<!-- python-doc-exec (native|mock|sudo): ([\w-]+\.py) -->\s*```python\n(.*?)\n```"


def tutorial_examples(kind: str) -> list[tuple[str, str]]:
    return [
        (filename, source)
        for path in sorted(TUTORIAL.glob("*.md"))
        for category, filename, source in re.findall(
            PATTERN, path.read_text(encoding="utf-8"), re.DOTALL
        )
        if category == kind
    ]
