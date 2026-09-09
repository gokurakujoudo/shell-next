"""In-memory backend adapter running the production command lifecycle."""

import asyncio
from collections import deque
from typing import TYPE_CHECKING

from shell_next.backends.mock.scenario import (
    Advance,
    Emit,
    MockExpectation,
    MockScenario,
    Receive,
)
from shell_next.errors import (
    InputError,
    MockUnexpectedInputError,
    PrivilegeAuthenticationError,
    SessionProtocolError,
)
from shell_next.models.commands import Command
from shell_next.models.privilege import PrivilegeReport
from shell_next.models.results import BackendStatus, CleanupReport

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle
    from shell_next.frontend.session import ShellSession


class MockDriver:
    """Deterministic transport that cannot start subprocesses or write files.

    :param scenario: Ordered commands, input, and output expectations.
    :param session: Owning frontend for simulated persistent state.
    """

    def __init__(self, scenario: MockScenario, session: ShellSession) -> None:
        """Initialize pure in-memory execution state.

        :param scenario: Strict expected behavior.
        :param session: Owning frontend.
        """
        self.scenario = scenario
        self.session = session
        self.active: MockExpectation | None = None
        self.inputs: deque[bytes | None] = deque()
        self.changed = asyncio.Event()
        self.handle: CommandHandle | None = None

    async def start(self) -> None:
        """Enter the mock without consulting or changing ambient process state."""

    def reserve(self, command: Command) -> MockExpectation:
        """Match and reserve the next command in deterministic FIFO order.

        :param command: Submitted process or native script description.
        :returns: The exact reserved expectation, even when other queued commands are stopped.
        :raises MockUnexpectedCommandError: No strict expectation matches.
        """
        return self.scenario.reserve(command)

    async def prepare(self, handle: CommandHandle) -> None:
        """Adopt the reserved expectation without filesystem or subprocess work.

        :param handle: Command receiving simulated transport behavior.
        """
        assert isinstance(handle.reservation, MockExpectation)
        self.active = handle.reservation
        self.handle = handle
        self.inputs.clear()

    async def execute(self, handle: CommandHandle) -> BackendStatus:
        """Emit deterministic events, wait for input, and advance only virtual time.

        :param handle: Command receiving output and readiness.
        :returns: Configured backend-native status.
        :raises MockUnexpectedInputError: Submitted input differs from the scenario.
        :raises TimeoutError: Virtual execution reaches its configured deadline.
        :raises InputError: An input failure was configured.
        :raises OSError: A startup failure was configured.
        :raises SessionProtocolError: A session loss was configured.
        """
        assert self.active is not None
        if handle.privilege.requested:
            request = handle.options.privilege
            for _ in range(min(self.active.authentication_prompts, request.attempts)):
                if request.password_provider is not None:
                    try:
                        await request.password_provider()
                    except Exception:
                        handle.privilege = PrivilegeReport(True, False)
                        raise PrivilegeAuthenticationError("Password provider failed") from None
                self.session.record("authenticate", "<redacted>")
            handle.privilege = PrivilegeReport(
                True,
                self.active.authenticated,
                min(self.active.authentication_prompts, request.attempts),
            )
            if not self.active.authenticated:
                handle.ready.set()
                return BackendStatus(126)
        handle.ready.set()
        elapsed = 0.0
        for step in self.active.steps:
            if isinstance(step, Emit):
                await handle.emit(step.stream, step.data)
            elif isinstance(step, Receive):
                await self.receive(step.data)
            elif isinstance(step, Advance):
                deadline = handle.options.timeouts.execution
                if deadline is not None and elapsed + step.seconds >= deadline:
                    self.scenario.elapsed += max(0, deadline - elapsed)
                    raise TimeoutError("Virtual command deadline expired")
                elapsed += step.seconds
                self.scenario.elapsed += step.seconds
            else:
                if step.kind == "input":
                    raise InputError("Simulated input failure")
                if step.kind == "startup":
                    raise OSError("Simulated startup failure")
                if step.kind == "session":
                    raise SessionProtocolError("Simulated session loss")
                handle.captures["stdout"].error = "Simulated capture failure"
        if self.active.cwd is not None:
            self.session.cwd = self.active.cwd
        for name, value in self.active.env:
            if value is None:
                self.session.environment.pop(name, None)
            else:
                self.session.environment[name] = value
        if any(self.inputs):
            raise MockUnexpectedInputError("Unexpected input remained after the scenario ended")
        return self.active.status

    async def receive(self, expected: bytes | None) -> None:
        """Match expected byte-stream input independently of transport chunk boundaries.

        :param expected: Required bytes, or an explicit EOF marker.
        :raises MockUnexpectedInputError: Bytes or EOF do not match the scenario.
        """
        offset = 0
        while True:
            while not self.inputs:
                assert self.handle is not None
                self.handle.virtual_blocked = True
                self.changed.clear()
                await self.changed.wait()
            actual = self.inputs.popleft()
            if expected is None:
                if actual is not None:
                    raise MockUnexpectedInputError("Expected stdin closure")
                return
            if actual is None:
                raise MockUnexpectedInputError("Input ended before the expected bytes")
            count = min(len(actual), len(expected) - offset)
            if actual[:count] != expected[offset : offset + count]:
                raise MockUnexpectedInputError("Input did not match the scenario")
            offset += count
            if len(actual) > count:
                self.inputs.appendleft(actual[count:])
            if offset == len(expected):
                return

    async def send(self, data: bytes) -> None:
        """Queue one in-memory input submission without retaining a history copy.

        :param data: Raw expected business input.
        """
        self.inputs.append(data)
        assert self.handle is not None
        self.handle.virtual_blocked = False
        self.changed.set()

    async def close_stdin(self) -> None:
        """Queue an explicit in-memory EOF operation."""
        self.inputs.append(None)
        assert self.handle is not None
        self.handle.virtual_blocked = False
        self.changed.set()

    async def finish(self) -> None:
        """Discard transient input payloads after finalization."""
        self.inputs.clear()
        self.active = None

    async def stop(self) -> CleanupReport:
        """Simulate forced session invalidation without signals or real processes.

        :returns: Deterministic successful containment report.
        """
        return CleanupReport(forced=True)

    async def close(self) -> CleanupReport:
        """Release in-memory input state without any operating-system side effect.

        :returns: Deterministic shutdown report.
        """
        self.inputs.clear()
        return CleanupReport()
