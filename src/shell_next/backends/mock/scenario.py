"""Strict, deterministic command expectations without operating-system side effects."""

from dataclasses import dataclass, field
from typing import Literal

from shell_next.errors import MockExpectationNotConsumedError, MockUnexpectedCommandError
from shell_next.models.commands import Command
from shell_next.models.config import validate_seconds
from shell_next.models.input import StreamName
from shell_next.models.representation import RecordRepr
from shell_next.models.results import BackendStatus


@dataclass(frozen=True, repr=False)
class Emit(RecordRepr):
    """Emit one raw mock output chunk.

    :param data: Raw bytes delivered to capture and prompt matching.
    :param stream: Destination transport, defaulting to stdout.
    """

    data: bytes
    stream: StreamName = "stdout"


@dataclass(frozen=True, repr=False)
class Receive(RecordRepr):
    """Require one input submission or explicit EOF.

    :param data: Expected bytes, or None for stdin closure; always hidden in repr.
    """

    data: bytes | None = field(repr=False)


@dataclass(frozen=True, repr=False)
class Advance(RecordRepr):
    """Advance virtual command time without sleeping.

    :param seconds: Nonnegative virtual duration in seconds.
    """

    seconds: float

    def __post_init__(self) -> None:
        """Reject virtual time moving backwards or becoming nonfinite.

        :raises ConfigurationError: The virtual duration is invalid.
        """
        validate_seconds(self.seconds, "virtual seconds")


@dataclass(frozen=True, repr=False)
class Failure(RecordRepr):
    """Inject a transport or protocol failure deterministically.

    :param kind: Input, output, startup, or session failure category.
    """

    kind: Literal["input", "output", "startup", "session"]


@dataclass(frozen=True, repr=False)
class MockExpectation(RecordRepr):
    """One expected command with ordered interaction and simulated native status.

    :param command: Exact expected structural process or script.
    :param steps: Ordered output, input, time, and failure steps.
    :param status: Native result after all interaction steps.
    :param cwd: Optional simulated persistent directory change.
    :param env: Simulated environment updates, hidden in repr; None removes a variable.
    :param authentication_prompts: Simulated private password requests; zero models a cache hit.
    :param authenticated: Whether simulated privilege authentication succeeds.
    """

    command: Command
    steps: tuple[Emit | Receive | Advance | Failure, ...] = ()
    status: BackendStatus = field(default_factory=lambda: BackendStatus(0))
    cwd: str | None = None
    env: tuple[tuple[str, str | None], ...] = field(default=(), repr=False)
    authentication_prompts: int = 0
    authenticated: bool = True


@dataclass(repr=False)
class MockScenario(RecordRepr):
    """FIFO expectations, strict by default, with deterministic observable history.

    :param expectations: Ordered expected commands.
    :param strict: Reject unexpected commands and unconsumed required expectations.
    :param calls: Observable operations; secrets must already be redacted.
    :param elapsed: Virtual monotonic seconds, starting at zero.
    :param cursor: Number of expectations reserved by submissions.
    """

    expectations: list[MockExpectation] = field(default_factory=list)
    strict: bool = True
    calls: list[tuple[object, ...]] = field(default_factory=list)
    elapsed: float = 0.0
    cursor: int = 0

    def reserve(self, command: Command) -> MockExpectation:
        """Consume the next command expectation without starting any execution.

        :param command: Submitted command description.
        :returns: The matching expectation or permissive empty result.
        :raises MockUnexpectedCommandError: Strict FIFO expectations do not match.
        """
        if self.cursor < len(self.expectations):
            expected = self.expectations[self.cursor]
            if expected.command == command:
                self.cursor += 1
                return expected
        if self.strict:
            raise MockUnexpectedCommandError("Command did not match the next scenario expectation")
        return MockExpectation(command)

    def assert_consumed(self) -> None:
        """Require all declared command expectations to have been submitted.

        :raises MockExpectationNotConsumedError: Strict expectations remain unused.
        """
        if self.strict and self.cursor != len(self.expectations):
            raise MockExpectationNotConsumedError("Required command expectations remain unused")

    def assert_called(self, command: Command) -> None:
        """Assert that a command was submitted through the normal frontend.

        :param command: Expected submitted description.
        :raises AssertionError: No matching submission exists.
        """
        assert ("submit", command) in self.calls, "Command was not submitted"
