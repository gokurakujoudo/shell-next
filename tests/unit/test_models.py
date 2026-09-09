import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

from shell_next import (
    Backend,
    CaptureConfig,
    CommandOptions,
    Expect,
    InputPlan,
    MockShellSession,
    PrivilegeRequest,
    ProcessCommand,
    Send,
    SessionConfig,
    SessionScript,
    StdinMode,
    TimeoutPolicy,
)
from shell_next.errors import ConfigurationError, PrivilegeCleanupError
from shell_next.models.capabilities import backend_capabilities
from shell_next.models.privilege import validate_privilege


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
@pytest.mark.parametrize(
    "field", ["execution", "acquire", "prepare", "soft_stop", "force_stop", "drain", "finalize"]
)
def test_deadlines_are_finite_nonnegative(duration: float, field: str) -> None:
    with pytest.raises(ConfigurationError):
        TimeoutPolicy(**{field: duration})


@pytest.mark.parametrize("command", ["", "bad\0name"])
def test_invalid_process_executable(command: str) -> None:
    with pytest.raises(ConfigurationError):
        ProcessCommand(command)


def test_values_are_immutable_and_reject_unrepresentable_text() -> None:
    with pytest.raises(ConfigurationError):
        ProcessCommand("exe", ("bad\0arg",))
    with pytest.raises(ConfigurationError):
        SessionScript("bad\0script")
    process = ProcessCommand("exe", ("a",))
    with pytest.raises(FrozenInstanceError):
        cast(Any, process).args = ()
    assert SessionScript("").text == ""
    assert "private" not in repr(Send(b"private", secret=True))


@pytest.mark.parametrize(
    "configuration",
    [
        {"tail_bytes": -1},
        {"match_bytes": 0},
        {"event_queue": 0},
    ],
)
def test_invalid_capture_bounds(configuration: dict[str, int]) -> None:
    with pytest.raises(ConfigurationError):
        CaptureConfig(
            tail_bytes=configuration.get("tail_bytes", 1),
            match_bytes=configuration.get("match_bytes", 1),
            event_queue=configuration.get("event_queue", 1),
        )


def test_discard_and_file_are_exclusive() -> None:
    with pytest.raises(ConfigurationError):
        CaptureConfig(discard=True, directory=Path("unused"))


def test_input_plan_ownership_and_expect_validation() -> None:
    with pytest.raises(ConfigurationError):
        CommandOptions(stdin=StdinMode.PLAN)
    with pytest.raises(ConfigurationError):
        CommandOptions(input_plan=InputPlan())
    assert CommandOptions(stdin=StdinMode.PLAN, input_plan=InputPlan()).input_plan is not None
    with pytest.raises(ConfigurationError):
        Expect(b"")
    with pytest.raises(ConfigurationError):
        Expect(b"x", timeout=-1)
    assert Expect(b"x", timeout=0).timeout == 0


@pytest.mark.parametrize("env", [{"": "x"}, {"a=b": "x"}, {"a": "x\0"}])
def test_environment_validation(env: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        SessionConfig(env=env)


def test_injection_is_absent_from_repr_equality_and_serialization() -> None:
    config = SessionConfig()
    original = SessionConfig()
    config._session_cls = MockShellSession
    assert config == original
    assert "MockShellSession" not in repr(config)
    assert "_session_cls" not in json.dumps(config.to_dict())


def test_privilege_validation_and_no_silent_cleanup_downgrade() -> None:
    with pytest.raises(ConfigurationError):
        PrivilegeRequest(attempts=0)
    with pytest.raises(ConfigurationError):
        PrivilegeRequest(interactive=True)
    for target in ("", "bad\0"):
        with pytest.raises(ConfigurationError):
            PrivilegeRequest(target_identity=target)
    capabilities = backend_capabilities(Backend.BASH)
    with pytest.raises(PrivilegeCleanupError):
        validate_privilege(
            PrivilegeRequest(requirement="elevated", strict_cleanup=True), capabilities
        )
    validate_privilege(PrivilegeRequest(), capabilities)
    validate_privilege(PrivilegeRequest(requirement="elevated"), capabilities)
    assert not backend_capabilities(Backend.CMD).functions
