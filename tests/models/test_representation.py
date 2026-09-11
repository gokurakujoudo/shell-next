from dataclasses import is_dataclass
from pathlib import Path

import pytest

import shell_next as api


def test_all_public_records_have_named_readable_representations() -> None:
    command = api.ProcessCommand("git", ("status", "--short"))
    result = api.CommandResult(
        "session",
        "command",
        api.Backend.BASH,
        "process",
        api.Outcome.EXITED,
        True,
        api.BackendStatus(0),
        0.0,
        1.0,
        command=command,
    )
    records = [
        command,
        result,
        api.SessionScript("echo hello"),
        api.BackendStatus(),
        api.OutputResult(),
        api.OutputEvent("command", 0, "stdout", 0, b"hello", 0.0),
        api.CleanupReport(),
        api.TimeoutPolicy(),
        api.CaptureConfig(),
        api.CommandOptions(),
        api.SessionConfig(),
        api.PrivilegeRequest(),
        api.PrivilegeReport(),
        api.InputPlan(),
        api.InputSummary(),
        api.Send(b"private"),
        api.SendLine(b"private"),
        api.Expect(b"ready"),
        api.CloseStdin(),
        api.SessionCapabilities(),
        api.SessionSnapshot("session", api.SessionState.OPEN, None, 0, "/", ()),
        api.CommandSnapshot("command", "finished", 5, 0, result),
        api.Emit(b"hello"),
        api.Receive(b"private"),
        api.Advance(1),
        api.Failure("input"),
        api.MockExpectation(command),
        api.MockScenario(),
    ]
    public_records = {name for name in api.__all__ if is_dataclass(getattr(api, name))}
    assert {type(record).__name__ for record in records} == public_records
    for record in records:
        rendered = repr(record)
        assert rendered.startswith(type(record).__name__ + "(") and rendered.endswith(")")
        assert " object at " not in rendered
        assert "<Backend:" not in rendered
        assert "private" not in rendered
    assert repr(command) == "ProcessCommand(executable='git', args=('status', '--short'))"
    assert "backend=Backend.BASH" in repr(result)
    assert "outcome=Outcome.EXITED" in repr(result)
    assert "success=True" in repr(result)


def test_large_payloads_collections_and_recursive_records_are_bounded() -> None:
    data = b"\x00\xff" * 100000
    output = api.OutputResult(received=len(data), tail=data, complete=False, end="truncated")
    text = repr(output)
    assert len(text) < 400 and "(200000 bytes)" in text
    assert "complete=False" in text and "end='truncated'" in text
    assert output.tail is data
    command = api.ProcessCommand("tool", tuple(f"arg-{number}" for number in range(10000)))
    assert "'arg-0'" in repr(command) and "'arg-4'" not in repr(command)
    assert "..." in repr(command) and len(repr(command)) < 150
    script = api.SessionScript("begin\n" + "x" * 100000 + "\nend")
    assert len(repr(script)) < 110 and "..." in repr(script)
    assert "\n" not in repr(script)
    scenario = api.MockScenario()
    scenario.calls.append(("cycle", scenario))
    assert "MockScenario(...)" in repr(scenario)
    assert len(repr(scenario)) < 300
    assert scenario.calls[0][1] is scenario


def test_nested_sensitive_fields_remain_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("repr must not perform I/O or call a secret provider")

    async def password_provider() -> bytes:
        forbidden()
        return b"unreachable"

    monkeypatch.setattr(Path, "open", forbidden)
    command = api.SessionScript("original-command-must-be-hidden")
    expectation = api.MockExpectation(command, env=(("TOKEN", "private-env"),))
    config = api.SessionConfig(
        env={"TOKEN": "private-env"},
        defaults=api.CommandOptions(
            privilege=api.PrivilegeRequest(interactive=True, password_provider=password_provider),
            stdin=api.StdinMode.PLAN,
            input_plan=api.InputPlan((api.Send(b"private-input", secret=True),)),
        ),
        _session_cls=api.MockShellSession,
    )
    result = api.CommandResult(
        "session",
        "command",
        api.Backend.BASH,
        "script",
        api.Outcome.EXITED,
        True,
        api.BackendStatus(0),
        0.0,
        1.0,
        command=command,
        stdout=api.OutputResult(path="must-not-open"),
    )
    snapshot = api.SessionSnapshot(
        "session",
        api.SessionState.OPEN,
        None,
        0,
        "/",
        (("TOKEN", "private-env"),),
    )
    for value in (config, expectation, snapshot, api.MockScenario([expectation]), result):
        rendered = repr(value)
        assert "private-env" not in rendered and "private-input" not in rendered
        assert "password_provider" not in rendered and "MockShellSession" not in rendered
    assert "original-command-must-be-hidden" not in repr(result)
    assert config.env["TOKEN"] == "private-env"
    assert snapshot.environment == (("TOKEN", "private-env"),)
