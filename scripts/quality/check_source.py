"""Enforce specification source policies without hiding executable lines in strings."""

import ast
import io
import tokenize
from pathlib import Path


def inspect_source(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    excluded: set[int] = set()
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) or (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            excluded.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and not (
                node.name.startswith("__") and node.name.endswith("__")
            ):
                errors.append(f"{path}:{node.lineno}: underscore-prefixed name {node.name}")
            doc = ast.get_docstring(node)
            if not doc:
                errors.append(f"{path}:{node.lineno}: missing docstring for {node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                for optional in (node.args.vararg, node.args.kwarg):
                    if optional is not None:
                        arguments.append(optional)
                for argument in arguments:
                    if argument.arg not in ("self", "cls") and f":param {argument.arg}:" not in doc:
                        errors.append(f"{path}:{node.lineno}: undocumented {argument.arg}")
                if node.returns and ast.unparse(node.returns) != "None" and ":returns:" not in doc:
                    errors.append(f"{path}:{node.lineno}: missing returns documentation")
    bearing: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type not in (
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
        ):
            bearing.update(range(token.start[0], token.end[0] + 1))
    count = len(bearing - excluded)
    if count > 200:
        errors.append(f"{path}: {count} code-bearing lines exceed 200")
    return errors


def main() -> None:
    errors = [
        error for path in Path("src/shell_next").rglob("*.py") for error in inspect_source(path)
    ]
    for error in errors:
        print(error)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
