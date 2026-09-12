import re
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import pytest

from shell_next import (
    Backend,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
    SessionScript,
    ShellSession,
    use_shell_session,
)
from tests.support.tutorials import ROOT, TUTORIAL, tutorial_examples


def test_tutorial_contents_and_exact_example_files() -> None:
    contents = (TUTORIAL / "index.md").read_text(encoding="utf-8")
    chapters = re.findall(r"^\d+\. \[.*?\]\(([^)]+\.md)\)$", contents, re.MULTILINE)
    assert chapters
    assert len(chapters) == len(set(chapters))
    assert chapters == sorted(chapters)
    assert set(chapters) == {path.name for path in TUTORIAL.glob("[0-9]*.md")}
    examples = [item for kind in ("native", "mock", "sudo") for item in tutorial_examples(kind)]
    assert len(examples) == len(chapters)
    assert {name for name, _ in examples} == {
        path.name for path in (ROOT / "examples").glob("*.py")
    }
    navigation = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for chapter in chapters:
        assert f"tutorials/{chapter}" in navigation
    for filename, source in examples:
        assert (ROOT / "examples" / filename).read_text(encoding="utf-8") == source + "\n"
        assert filename.removesuffix(".py") + ".md" in chapters


@pytest.mark.parametrize(
    "filename,source",
    tutorial_examples("mock"),
    ids=[name for name, _ in tutorial_examples("mock")],
)
def test_mock_tutorial_source(filename: str, source: str, directory: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=directory, capture_output=True, timeout=30
    )
    assert result.returncode == 0, (filename, result.stdout, result.stderr)


@pytest.mark.parametrize("mode", ["noninteractive", "interactive", "session"])
@pytest.mark.parametrize("prompts", [0, 1])
async def test_sudo_tutorial_with_private_mock_authentication(mode: str, prompts: int) -> None:
    filename, source = tutorial_examples("sudo")[0]
    namespace: dict[str, Any] = {"__name__": "tutorial_example"}
    exec(compile(source, filename, "exec"), namespace)
    command = ProcessCommand("id", ("-u",))
    expected_prompts = prompts if mode != "noninteractive" else 0
    expectations = [
        MockExpectation(command, (Emit(b"0\n"),), authentication_prompts=expected_prompts)
    ]
    if mode == "session":
        expectations.append(
            MockExpectation(
                SessionScript("demo_elevated=1\nid -u"),
                (Emit(b"0\n"),),
                authentication_prompts=expected_prompts,
            )
        )
        expectations.append(
            MockExpectation(
                SessionScript('printf "%s" "${demo_elevated-unset}"'), (Emit(b"unset"),)
            )
        )
    scenario = MockScenario(expectations)
    supplied: list[bytes] = []

    async def provider() -> bytes:
        supplied.append(b"tutorial-test-secret")
        return supplied[-1]

    @asynccontextmanager
    async def factory(config: SessionConfig) -> AsyncIterator[ShellSession]:
        config._session_cls = MockShellSession.configured(scenario)
        async with use_shell_session(config) as shell:
            yield shell

    namespace["password_provider"] = provider
    namespace["use_shell_session"] = factory
    main = cast(Callable[[Backend, str], Awaitable[None]], namespace["main"])
    await main(Backend.BASH, mode)
    assert len(supplied) == (1 if mode == "session" else expected_prompts)
    assert "tutorial-test-secret" not in repr(scenario.calls)
    scenario.assert_consumed()


@pytest.mark.parametrize("backend", [Backend.POWERSHELL, Backend.CMD])
async def test_sudo_tutorial_reports_windows_capability(backend: Backend) -> None:
    filename, source = tutorial_examples("sudo")[0]
    namespace: dict[str, Any] = {"__name__": "tutorial_example"}
    exec(compile(source, filename, "exec"), namespace)
    scenario = MockScenario()

    @asynccontextmanager
    async def factory(config: SessionConfig) -> AsyncIterator[ShellSession]:
        config._session_cls = MockShellSession.configured(scenario)
        async with use_shell_session(config) as shell:
            yield shell

    namespace["use_shell_session"] = factory
    main = cast(Callable[[Backend, str], Awaitable[None]], namespace["main"])
    await main(backend, "noninteractive")
    assert not any(call[0] == "submit" for call in scenario.calls)
