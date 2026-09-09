"""Persistent asynchronous shell sessions and deterministic downstream testing."""

from shell_next.backends.mock.scenario import (
    Advance,
    Emit,
    Failure,
    MockExpectation,
    MockScenario,
    Receive,
)
from shell_next.backends.mock.session import MockShellSession
from shell_next.frontend.handle import CommandHandle
from shell_next.frontend.session import ShellSession, use_shell_session
from shell_next.models.capabilities import SessionCapabilities
from shell_next.models.commands import Command, ProcessCommand, SessionScript
from shell_next.models.config import CaptureConfig, CommandOptions, SessionConfig, TimeoutPolicy
from shell_next.models.input import CloseStdin, Expect, InputPlan, InputSummary, Send, SendLine
from shell_next.models.privilege import PasswordProvider, PrivilegeReport, PrivilegeRequest
from shell_next.models.results import (
    BackendStatus,
    CleanupReport,
    CommandResult,
    CommandSnapshot,
    OutputEvent,
    OutputResult,
    SessionSnapshot,
)
from shell_next.models.state import Backend, ConcurrencyPolicy, Outcome, SessionState, StdinMode

__all__ = [
    "Advance",
    "Backend",
    "BackendStatus",
    "CaptureConfig",
    "CleanupReport",
    "CloseStdin",
    "Command",
    "CommandHandle",
    "CommandOptions",
    "CommandResult",
    "CommandSnapshot",
    "ConcurrencyPolicy",
    "Emit",
    "Expect",
    "Failure",
    "InputPlan",
    "InputSummary",
    "MockExpectation",
    "MockScenario",
    "MockShellSession",
    "Outcome",
    "OutputEvent",
    "OutputResult",
    "PasswordProvider",
    "PrivilegeReport",
    "PrivilegeRequest",
    "ProcessCommand",
    "Receive",
    "Send",
    "SendLine",
    "SessionCapabilities",
    "SessionConfig",
    "SessionScript",
    "SessionSnapshot",
    "SessionState",
    "ShellSession",
    "StdinMode",
    "TimeoutPolicy",
    "use_shell_session",
]
"""Curated public API names; transport modules remain implementation details."""
