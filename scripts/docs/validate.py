"""Validate rendered documentation links, fragments, assets, and the supplied logo."""

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is not None:
                if name in ("href", "src"):
                    self.links.append(value)
                elif name == "id":
                    self.ids.add(value)


def validate(directory: Path, base_path: str = "/shell-next/") -> list[str]:
    directory = directory.resolve()
    pages = {path: Page(path) for path in directory.rglob("*.html")}
    errors: list[str] = []
    for path, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            if url.path.startswith("/"):
                if not url.path.startswith(base_path):
                    errors.append(f"{path.relative_to(directory)}: outside site {link}")
                    continue
                target = (directory / unquote(url.path.removeprefix(base_path))).resolve()
            elif url.path:
                target = (path.parent / unquote(url.path)).resolve()
            else:
                target = path
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{path.relative_to(directory)}: missing {link}")
            elif (
                url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids
            ):
                errors.append(f"{path.relative_to(directory)}: missing fragment {link}")
    if not pages:
        errors.append("No generated HTML pages found")
    return errors


def main() -> None:
    directory = Path("site")
    errors = validate(directory)
    logo = Path("shell-next-logo.png").read_bytes()
    for destination in (
        Path("docs/assets/shell-next-logo.png"),
        directory / "assets/shell-next-logo.png",
    ):
        if (
            not destination.is_file()
            or hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(logo).digest()
        ):
            errors.append(f"Logo differs from supplied image: {destination}")
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print("Documentation links, fragments, assets, and original logo verified")


if __name__ == "__main__":
    main()
