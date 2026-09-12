"""Validated configuration with a nonserializing session injection point."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shell_next.errors import ConfigurationError
from shell_next.models.input import InputPlan
from shell_next.models.privilege import PrivilegeRequest, encode_password
from shell_next.models.representation import RecordRepr
from shell_next.models.state import Backend, ConcurrencyPolicy, StdinMode

if TYPE_CHECKING:
    from shell_next.frontend.session import ShellSession


def validate_seconds(value: float | None, name: str) -> None:
    """Require finite nonnegative seconds, allowing an explicitly absent deadline.

    :param value: Seconds or no deadline.
    :param name: Field name used in validation errors.
    :raises ConfigurationError: The duration is negative or not finite.
    """
    if value is not None and (not math.isfinite(value) or value < 0):
        raise ConfigurationError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True, repr=False)
class TimeoutPolicy(RecordRepr):
    """Independent execution and cleanup budgets, all measured in seconds.

    Defaults are package policy, not operating-system guarantees: cleanup gets
    short independent budgets to retain ownership without waiting indefinitely.

    :param execution: Execution deadline; None permits unlimited execution.
    :param acquire: Lease acquisition deadline, excluding actual execution.
    :param prepare: Command preparation deadline.
    :param soft_stop: Grace period after a soft termination request.
    :param force_stop: Wait after forced termination.
    :param drain: Time allowed for remaining stream bytes.
    :param finalize: Capture sealing deadline.
    """

    execution: float | None = None
    acquire: float | None = None
    prepare: float = 10.0
    soft_stop: float = 0.25
    force_stop: float = 5.0
    drain: float = 2.0
    finalize: float = 5.0

    def __post_init__(self) -> None:
        """Validate all duration fields.

        :raises ConfigurationError: A duration is negative or nonfinite.
        """
        for name in self.__dataclass_fields__:
            validate_seconds(getattr(self, name), name)


@dataclass(frozen=True, repr=False)
class CaptureConfig(RecordRepr):
    """Bounded capture limits; file destinations are opt-in and never overwritten.

    Defaults are package-selected byte and event counts: 64 KiB tails and match
    windows bound memory, while 128 events allow brief consumer scheduling gaps.

    :param tail_bytes: Maximum retained bytes per stream; zero discards the tail.
    :param match_bytes: Maximum bytes per prompt-matching window.
    :param event_queue: Maximum events buffered for each subscriber.
    :param directory: Optional directory for unique complete capture files.
    :param discard: Explicitly discard output while still counting received bytes.
    """

    tail_bytes: int = 65536
    match_bytes: int = 65536
    event_queue: int = 128
    directory: Path | None = None
    discard: bool = False

    def __post_init__(self) -> None:
        """Reject unbounded or inconsistent capture settings.

        :raises ConfigurationError: Bounds are invalid or discard requests files.
        """
        if self.tail_bytes < 0 or self.match_bytes < 1 or self.event_queue < 1:
            raise ConfigurationError("Capture bounds must be nonnegative; windows must be positive")
        if self.discard and self.directory is not None:
            raise ConfigurationError("Discard mode cannot persist files")


@dataclass(frozen=True, repr=False)
class CommandOptions(RecordRepr):
    """Per-command lifecycle configuration, measured by the nested policies.

    :param timeouts: Execution, acquisition, and cleanup budgets.
    :param stdin: One owner for business stdin; defaults to closed.
    :param input_plan: Required when stdin is plan; otherwise forbidden.
    :param check: Raise a typed exception only after unsuccessful finalization.
    :param privilege: Backend-neutral identity request.
    :param tags: User metadata copied into immutable final results.
    """

    timeouts: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    stdin: StdinMode = StdinMode.CLOSED
    input_plan: InputPlan | None = None
    check: bool = False
    privilege: PrivilegeRequest = field(default_factory=PrivilegeRequest)
    tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the exclusive source of business input.

        :raises ConfigurationError: A plan and stdin ownership disagree.
        """
        object.__setattr__(self, "stdin", StdinMode(self.stdin))
        if (self.stdin == StdinMode.PLAN) != (self.input_plan is not None):
            raise ConfigurationError("Plan mode requires exactly one input plan")


@dataclass(repr=False)
class SessionConfig(RecordRepr):
    """Session setup and the official downstream dependency injection point.

    :param backend: Native shell language.
    :param cwd: Initial working directory; None inherits the production parent.
    :param env: Initial environment overrides; never modifies the Python parent.
    :param defaults: Default command options.
    :param capture: Per-command output bounds and optional file capture.
    :param concurrency: Immediate rejection or FIFO queuing.
    :param startup_timeout: Startup budget in seconds, defaulting to ten.
    :param shutdown_timeout: Shutdown budget in seconds, defaulting to ten.
    :param executable: Optional shell executable path.
    :param _session_cls: Test implementation; excluded from repr, equality and serialization.
    :param sudo_password: Optional upfront sudo secret, normalized to UTF-8 bytes.
        Used only for elevated requests without a provider. Excluded from repr,
        equality, and to_dict; retained in this caller-owned configuration.
    """

    backend: Backend = Backend.BASH
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict, repr=False)
    defaults: CommandOptions = field(default_factory=CommandOptions)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    concurrency: ConcurrencyPolicy = ConcurrencyPolicy.REJECT
    startup_timeout: float = 10.0
    shutdown_timeout: float = 10.0
    executable: str | None = None
    _session_cls: type[ShellSession] | None = field(default=None, repr=False, compare=False)
    sudo_password: str | bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate setup without starting processes or consulting ambient state.

        :raises ConfigurationError: A duration, environment entry, or password is invalid.
        """
        self.backend = Backend(self.backend)
        self.concurrency = ConcurrencyPolicy(self.concurrency)
        self.sudo_password = encode_password(self.sudo_password)
        validate_seconds(self.startup_timeout, "startup_timeout")
        validate_seconds(self.shutdown_timeout, "shutdown_timeout")
        if any(not k or "=" in k or "\0" in k + v for k, v in self.env.items()):
            raise ConfigurationError("Invalid environment name or value")

    def to_dict(self) -> dict[str, Any]:
        """Serialize public setup without implementation classes or secret suppliers.

        :returns: Plain configuration values suitable for JSON serialization.
        """
        return {
            "backend": self.backend.value,
            "cwd": self.cwd,
            "env": dict(self.env),
            "concurrency": self.concurrency.value,
            "startup_timeout": self.startup_timeout,
            "shutdown_timeout": self.shutdown_timeout,
            "executable": self.executable,
        }
