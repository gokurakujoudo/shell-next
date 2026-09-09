"""Dimensionless lifecycle values, chosen to keep wire and result values readable."""

from enum import StrEnum


class Backend(StrEnum):
    """Native language identifiers; these names select, rather than translate, scripts."""

    BASH = "bash"
    POWERSHELL = "powershell"
    CMD = "cmd"


class ConcurrencyPolicy(StrEnum):
    """Execution-lease policy: immediate rejection or FIFO waiting."""

    REJECT = "reject"
    QUEUE = "queue"


class SessionState(StrEnum):
    """One-way session lifecycle; broken sessions are never restarted implicitly."""

    NEW = "new"
    OPEN = "open"
    BROKEN = "broken"
    CLOSING = "closing"
    CLOSED = "closed"


class Outcome(StrEnum):
    """Normalized reasons for command completion, independent of native exit codes."""

    EXITED = "exited"
    TIMEOUT = "timeout"
    STOPPED = "stopped"
    STARTUP_FAILURE = "startup_failure"
    INPUT_FAILURE = "input_failure"
    OUTPUT_FAILURE = "output_failure"
    SESSION_LOST = "session_lost"
    INTERNAL_FAILURE = "internal_failure"


class StdinMode(StrEnum):
    """Single-writer ownership: no input, ordered plan, or caller-controlled input."""

    CLOSED = "closed"
    PLAN = "plan"
    MANUAL = "manual"
