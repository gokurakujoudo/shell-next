"""Backend-neutral privilege requests and payload-free reports."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from shell_next.errors import (
    ConfigurationError,
    PrivilegeCleanupError,
    PrivilegeUnsupportedError,
)
from shell_next.models.capabilities import SessionCapabilities

type PasswordProvider = Callable[[], Awaitable[bytes]]
"""Asynchronous secret supplier, invoked only after sudo requests authentication."""


@dataclass(frozen=True)
class PrivilegeRequest:
    """A capability-checked request, never an implicit Windows UAC action.

    :param requirement: Inherited identity or active elevation.
    :param target_identity: Optional sudo target user.
    :param interactive: Permit separate password authentication.
    :param strict_cleanup: Require guaranteed privileged descendant cleanup.
    :param attempts: Maximum authentication attempts, a positive count.
    :param password_provider: Secret supplier, excluded from repr and equality.
    """

    requirement: Literal["inherited", "elevated"] = "inherited"
    target_identity: str | None = None
    interactive: bool = False
    strict_cleanup: bool = False
    attempts: int = 1
    password_provider: PasswordProvider | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate requests before any privilege transport is started.

        :raises ConfigurationError: The request is inconsistent or invalid.
        """
        if self.requirement not in ("inherited", "elevated") or self.attempts < 1:
            raise ConfigurationError("Invalid privilege requirement or attempt count")
        if self.interactive and self.password_provider is None:
            raise ConfigurationError("Interactive privilege requires a password provider")
        if self.target_identity is not None and (
            not self.target_identity or "\0" in self.target_identity
        ):
            raise ConfigurationError("Invalid target identity")


@dataclass(frozen=True)
class PrivilegeReport:
    """Secret-free privilege outcome.

    :param requested: Active elevation was requested.
    :param authenticated: Authentication completed successfully.
    :param attempts: Password submissions, counted without retaining values.
    :param strict_cleanup: Privileged containment was guaranteed.
    """

    requested: bool = False
    authenticated: bool = False
    attempts: int = 0
    strict_cleanup: bool = False


def validate_privilege(request: PrivilegeRequest, capabilities: SessionCapabilities) -> None:
    """Fail closed when an explicit privilege guarantee cannot be provided.

    :param request: Requested execution identity and containment.
    :param capabilities: Runtime backend capabilities.
    :raises PrivilegeUnsupportedError: Active elevation is unavailable.
    :raises PrivilegeCleanupError: Strict privileged cleanup is unavailable.
    """
    if request.requirement == "elevated":
        if not capabilities.privilege_execution:
            raise PrivilegeUnsupportedError("Active elevation is unsupported by this backend")
        if request.strict_cleanup and not capabilities.strict_privileged_cleanup:
            raise PrivilegeCleanupError("Strict privileged cleanup cannot be guaranteed")
