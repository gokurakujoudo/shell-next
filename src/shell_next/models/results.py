"""Immutable execution, capture, cleanup, and snapshot records."""

from dataclasses import dataclass, field

from shell_next.models.commands import Command
from shell_next.models.input import InputSummary, StreamName
from shell_next.models.privilege import PrivilegeReport
from shell_next.models.state import Backend, Outcome, SessionState


@dataclass(frozen=True)
class BackendStatus:
    """Native status details, deliberately separate from the normalized outcome.

    :param code: Process exit code, Bash status, or cmd ERRORLEVEL.
    :param last_success: PowerShell's final success flag, if available.
    :param native_exit_code: PowerShell's last native executable status.
    :param terminating_error: Whether PowerShell caught a terminating error.
    """

    code: int | None = None
    last_success: bool | None = None
    native_exit_code: int | None = None
    terminating_error: bool = False


@dataclass(frozen=True)
class OutputResult:
    """Sealed stream accounting with byte counts and explicit completeness.

    :param received: Bytes received from the transport.
    :param committed: Bytes durably flushed to a configured file.
    :param tail: Bounded final raw bytes.
    :param path: Capture file path, if configured.
    :param end: EOF, truncation, storage failure, or forced closure.
    :param complete: All transport bytes were retained by the selected destination.
    :param sealed: Destination finalization succeeded.
    :param unread_possible: Cleanup may have left unread transport bytes.
    """

    received: int = 0
    committed: int = 0
    tail: bytes = b""
    path: str | None = None
    end: str = "eof"
    complete: bool = True
    sealed: bool = True
    unread_possible: bool = False


@dataclass(frozen=True)
class OutputEvent:
    """A raw stream chunk with stable sequence and byte offset.

    :param command_id: Owning command identifier.
    :param sequence: Monotonically increasing command-local event number.
    :param stream: Transport stream name.
    :param offset: Starting byte offset within this stream.
    :param data: Raw chunk bytes.
    :param timestamp: Monotonic seconds, or virtual seconds in mocks.
    :param persisted: Whether these bytes are durably committed.
    :param logical_stream: Optional backend-specific label.
    """

    command_id: str
    sequence: int
    stream: StreamName
    offset: int
    data: bytes
    timestamp: float
    persisted: bool = False
    logical_stream: str | None = None


@dataclass(frozen=True)
class CleanupReport:
    """Termination and cleanup evidence, without inferring unverified guarantees.

    :param soft_stop: A soft termination was requested.
    :param forced: Forceful termination was requested.
    :param contained: The process containment unit was successfully cleaned up.
    :param errors: Secondary cleanup failures, without command payloads.
    """

    soft_stop: bool = False
    forced: bool = False
    contained: bool = True
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandResult:
    """One final command result, including execution and capture independently.

    :param session_id: Owning session identifier.
    :param command_id: Command identifier.
    :param backend: Native shell language.
    :param kind: Structural process or native script.
    :param outcome: Normalized completion reason.
    :param success: Execution and capture both met their contracts.
    :param status: Backend-native status values.
    :param started: Execution start in monotonic seconds; None if never started.
    :param finished: Finalization time in monotonic seconds.
    :param stdout: Standard output accounting.
    :param stderr: Standard error accounting.
    :param input: Secret-free input accounting.
    :param privilege: Secret-free privilege accounting.
    :param cleanup: Termination and containment evidence.
    :param secondary_errors: Additional failures that did not replace the primary outcome.
    :param tags: Immutable user key/value pairs.
    :param session_reusable: Session protocol was healthy when finalization ended.
    :param command: Original submitted command, excluded from repr. None is allowed
        for manually constructed legacy results; session results always retain it.
    """

    session_id: str
    command_id: str
    backend: Backend
    kind: str
    outcome: Outcome
    success: bool
    status: BackendStatus
    started: float | None
    finished: float
    stdout: OutputResult = field(default_factory=OutputResult)
    stderr: OutputResult = field(default_factory=OutputResult)
    input: InputSummary = field(default_factory=InputSummary)
    privilege: PrivilegeReport = field(default_factory=PrivilegeReport)
    cleanup: CleanupReport = field(default_factory=CleanupReport)
    secondary_errors: tuple[str, ...] = ()
    tags: tuple[tuple[str, str], ...] = ()
    session_reusable: bool = True
    command: Command | None = field(default=None, repr=False)

    def stdout_str(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Decode the retained stdout tail without reading a capture file.

        :param encoding: Python text codec name; defaults to UTF-8.
        :param errors: Decode error handler; replacement tolerates truncated characters.
        :returns: Tail text, possibly incomplete when byte capture was truncated.
        :raises UnicodeError: Decoding fails with the selected error handler.
        :raises LookupError: The codec or required error handler is unknown.
        """
        return self.stdout.tail.decode(encoding, errors)

    def stderr_str(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Decode the retained stderr tail without reading a capture file.

        :param encoding: Python text codec name; defaults to UTF-8.
        :param errors: Decode error handler; replacement tolerates truncated characters.
        :returns: Tail text, possibly incomplete when byte capture was truncated.
        :raises UnicodeError: Decoding fails with the selected error handler.
        :raises LookupError: The codec or required error handler is unknown.
        """
        return self.stderr.tail.decode(encoding, errors)


@dataclass(frozen=True)
class SessionSnapshot:
    """In-memory session view, requiring no implicit shell command.

    :param session_id: Session identifier.
    :param state: Current lifecycle state.
    :param active_command: Active or first queued command identifier, if any.
    :param queued: Number of submitted commands not yet executing.
    :param cwd: Last explicitly observed directory, possibly stale after scripts.
    :param environment: Last explicitly observed environment, possibly stale after scripts.
    """

    session_id: str
    state: SessionState
    active_command: str | None
    queued: int
    cwd: str | None
    environment: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CommandSnapshot:
    """In-memory view of one queued, active, or finalized command.

    :param command_id: Command identifier.
    :param state: Queued, running, or finished.
    :param stdout_bytes: Standard output bytes captured so far.
    :param stderr_bytes: Standard error bytes captured so far.
    :param result: Final immutable result, if available.
    """

    command_id: str
    state: str
    stdout_bytes: int
    stderr_bytes: int
    result: CommandResult | None
