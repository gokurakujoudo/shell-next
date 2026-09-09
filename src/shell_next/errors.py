"""Stable error categories shared by live sessions and deterministic mocks."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shell_next.models.results import CommandResult


class ShellError(Exception):
    """Base class for errors intentionally reported by this package."""


class ConfigurationError(ShellError, ValueError):
    """A configuration value violates the public contract."""


class CapabilityError(ShellError):
    """The requested behavior is unavailable in the selected backend."""


class SessionError(ShellError):
    """A session cannot satisfy a lifecycle operation."""


class SessionStartupError(SessionError):
    """The persistent shell failed to start or complete its handshake."""


class SessionBusyError(SessionError):
    """A command already owns the session execution lease."""


class SessionReentrancyError(SessionBusyError):
    """A scoped command owner attempted to acquire its own execution lease."""


class SessionBrokenError(SessionError):
    """The session protocol can no longer be trusted."""


class SessionClosedError(SessionError):
    """The session is not open for submissions."""


class SessionProtocolError(SessionError):
    """The shell lost or corrupted its private control protocol."""


class CommandError(ShellError):
    """An unsuccessful, finalized command result.

    :param result: Immutable result retained for caller inspection.
    """

    def __init__(self, result: CommandResult) -> None:
        """Keep the finalized result without including command text or input.

        :param result: Unsuccessful command result.
        """
        self.result = result
        super().__init__(f"Command {result.command_id}: {result.outcome}")


class CommandStartupError(CommandError):
    """An external executable or command could not start."""


class CommandFailedError(CommandError):
    """A command completed with a backend failure status."""


class CommandTimeoutError(CommandError):
    """The execution deadline expired and cleanup completed."""


class CommandStoppedError(CommandError):
    """The caller requested command termination."""


class InputError(ShellError):
    """Input transport or prompt matching failed."""


class InteractionError(CommandError):
    """An automatic input operation failed during execution."""


class CaptureError(ShellError):
    """An output capture destination could not retain output."""


class OutputSubscriberError(CaptureError):
    """A bounded subscriber fell behind; primary capture continues."""


class PrivilegeError(ShellError):
    """Privilege preparation or execution failed."""


class PrivilegeUnsupportedError(PrivilegeError, CapabilityError):
    """The backend cannot actively elevate a command."""


class PrivilegeAuthenticationError(PrivilegeError):
    """Sudo authentication failed without exposing credentials."""


class PrivilegeExecutionError(PrivilegeError):
    """The authenticated privilege request could not execute."""


class PrivilegeCleanupError(PrivilegeError, CapabilityError):
    """Strict containment of privileged descendants cannot be guaranteed."""


class MockExpectationError(ShellError, AssertionError):
    """A strict mock expectation was violated."""


class MockUnexpectedCommandError(MockExpectationError):
    """No remaining expectation matches the submitted command."""


class MockUnexpectedInputError(MockExpectationError):
    """Input differs from the next expected transport operation."""


class MockExpectationNotConsumedError(MockExpectationError):
    """Required expectations remain at scenario closure."""
