"""Immutable ordered input instructions and transport summaries."""

from dataclasses import dataclass, field
from typing import Literal

from shell_next.errors import ConfigurationError

type StreamName = Literal["stdout", "stderr", "terminal"]
"""Transport labels, shared across backends; terminal is reserved for capable transports."""
type MatchStream = Literal["stdout", "stderr", "either"]
"""Literal match destinations; either searches each stream independently."""


@dataclass(frozen=True)
class Send:
    """Submit bytes once without implying that a target consumed them.

    :param data: Bytes to submit; omitted from representations to protect secrets.
    :param secret: Redact the payload from observable call history.
    """

    data: bytes = field(repr=False)
    secret: bool = False


@dataclass(frozen=True)
class SendLine(Send):
    """Submit bytes followed by LF, including on Windows binary transports.

    :param data: Bytes preceding the newline; omitted from representations.
    :param secret: Redact the payload from observable call history.
    """


@dataclass(frozen=True)
class Expect:
    """Wait for a literal byte pattern in a bounded stream window.

    :param pattern: Nonempty bytes, potentially spanning read chunks.
    :param stream: Stream to search, or either independent stream.
    :param timeout: Optional observation timeout in seconds.
    """

    pattern: bytes
    stream: MatchStream = "stdout"
    timeout: float | None = None

    def __post_init__(self) -> None:
        """Validate pattern and deadline without running an input operation.

        :raises ConfigurationError: Pattern, stream, or timeout is invalid.
        """
        if not self.pattern or self.stream not in ("stdout", "stderr", "either"):
            raise ConfigurationError("Expect requires a pattern and a valid stream")
        if self.timeout is not None and self.timeout < 0:
            raise ConfigurationError("Expect timeout must be nonnegative")


@dataclass(frozen=True)
class CloseStdin:
    """Close business stdin explicitly after preceding plan operations."""


@dataclass(frozen=True)
class InputPlan:
    """Sequential single-writer input automation.

    :param steps: Ordered instructions, copied to an immutable tuple.
    """

    steps: tuple[Send | SendLine | Expect | CloseStdin, ...] = ()

    def __post_init__(self) -> None:
        """Freeze the caller's sequence to prevent mid-command mutation."""
        object.__setattr__(self, "steps", tuple(self.steps))


@dataclass(frozen=True)
class InputSummary:
    """Payload-free input accounting, measured in bytes.

    :param accepted: Bytes accepted by the package writer.
    :param submitted: Bytes for which transport submission completed.
    :param state: Transport state; submission does not imply target consumption.
    :param closed: Whether business stdin was closed.
    """

    accepted: int = 0
    submitted: int = 0
    state: str = "idle"
    closed: bool = False
