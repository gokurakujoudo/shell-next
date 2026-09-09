"""Managed command observation, input, and stop interfaces."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import TYPE_CHECKING

from shell_next.errors import (
    CommandFailedError,
    CommandStartupError,
    CommandStoppedError,
    CommandTimeoutError,
    InputError,
    InteractionError,
    PrivilegeAuthenticationError,
)
from shell_next.frontend.capture import StreamCapture
from shell_next.frontend.output import OutputHub
from shell_next.models.commands import Command
from shell_next.models.config import CommandOptions
from shell_next.models.input import InputSummary, MatchStream, StreamName
from shell_next.models.privilege import PrivilegeReport
from shell_next.models.results import CommandResult, CommandSnapshot, OutputEvent
from shell_next.models.state import Outcome, StdinMode

if TYPE_CHECKING:
    from shell_next.frontend.session import ShellSession


class CommandHandle:
    """Session-owned command with cancellation-isolated observation.

    :param session: Owning session.
    :param command_id: Unique command identifier.
    :param command: Validated structural process or script.
    :param options: Resolved command lifecycle options.
    """

    def __init__(
        self, session: ShellSession, command_id: str, command: Command, options: CommandOptions
    ) -> None:
        """Create bounded command state without scheduling subprocess work.

        :param session: Owning session.
        :param command_id: Unique command identifier.
        :param command: Command description.
        :param options: Lifecycle options.
        """
        self.session = session
        self.command_id = command_id
        self.command = command
        self.options = options
        self.reservation: object | None = None
        self.startup_failed = False
        self.future: asyncio.Future[CommandResult] = asyncio.get_running_loop().create_future()
        self.ready = asyncio.Event()
        self.stop_requested = asyncio.Event()
        self.writer_lock = asyncio.Lock()
        self.input = InputSummary()
        self.privilege = PrivilegeReport(requested=options.privilege.requirement == "elevated")
        self.state = "queued"
        self.result: CommandResult | None = None
        self.hub = OutputHub(command_id, session.config.capture, session.clock)
        directory = session.config.capture.directory
        self.captures = {
            name: StreamCapture(
                session.config.capture,
                directory / f"{command_id}.{name}" if directory is not None else None,
            )
            for name in ("stdout", "stderr")
        }

    async def wait(self, wait_timeout: float | None = None) -> CommandResult:
        """Observe completion; cancelling this wait does not stop the command.

        :param wait_timeout: Independent observation limit in seconds.
        :returns: The immutable finalized result.
        :raises TimeoutError: Only this caller's wait deadline expired.
        :raises CommandFailedError: check=True and native execution failed.
        :raises CommandTimeoutError: check=True and execution timed out.
        :raises CommandStoppedError: check=True and termination was requested.
        :raises CommandStartupError: check=True and command startup failed.
        :raises InteractionError: check=True and automatic input failed.
        """
        async with asyncio.timeout(wait_timeout):
            result = await asyncio.shield(self.future)
        if self.options.check and not result.success:
            if result.outcome == Outcome.STARTUP_FAILURE and result.privilege.requested:
                raise PrivilegeAuthenticationError("Privilege authentication failed", result)
            exception = {
                Outcome.TIMEOUT: CommandTimeoutError,
                Outcome.STOPPED: CommandStoppedError,
                Outcome.STARTUP_FAILURE: CommandStartupError,
                Outcome.INPUT_FAILURE: InteractionError,
            }.get(result.outcome, CommandFailedError)
            raise exception(result)
        return result

    async def stop(self) -> CommandResult:
        """Request termination and await finalized cleanup without applying check.

        :returns: Final immutable result, including any interruption damage.
        """
        self.session.record("stop", self.command_id)
        self.stop_requested.set()
        return await asyncio.shield(self.future)

    async def send(self, data: bytes, *, secret: bool = False) -> InputSummary:
        """Submit manual bytes exactly once through the command's logical writer.

        :param data: Bytes to submit.
        :param secret: Redact the payload from mock call history.
        :returns: Current payload-free input accounting.
        :raises InputError: Stdin is closed, unavailable, or owned by a plan.
        """
        if self.options.stdin != StdinMode.MANUAL:
            raise InputError("Manual input requires stdin='manual'")
        return await self.write_input(data, secret)

    async def write_input(self, data: bytes, secret: bool) -> InputSummary:
        """Serialize one authorized manual or planned transport operation.

        :param data: Bytes to submit once.
        :param secret: Redact the payload in observable call history.
        :returns: Input accounting after successful transport submission.
        :raises InputError: Input is closed or the transport failed.
        """
        await self.ready.wait()
        async with self.writer_lock:
            if self.input.closed or self.future.done():
                raise InputError("Command stdin is closed")
            self.input = replace(
                self.input, accepted=self.input.accepted + len(data), state="accepted"
            )
            self.session.record("send", self.command_id, "<redacted>" if secret else data)
            try:
                await self.session.driver.send(data)
            except asyncio.CancelledError:
                self.input = replace(self.input, state="aborted")
                raise
            except (OSError, ConnectionError) as exc:
                self.input = replace(self.input, state="failed")
                raise InputError("Input transport failed; input was not retried") from exc
            self.input = replace(
                self.input, submitted=self.input.submitted + len(data), state="submitted"
            )
            return self.input

    async def sendline(self, data: bytes, *, secret: bool = False) -> InputSummary:
        """Submit bytes followed by LF through the manual writer.

        :param data: Bytes preceding the newline.
        :param secret: Redact the complete submission from call history.
        :returns: Payload-free input accounting.
        :raises InputError: Manual submission is unavailable or fails.
        """
        return await self.send(data + b"\n", secret=secret)

    async def close_stdin(self) -> None:
        """Idempotently close business input without closing shell control input."""
        await self.ready.wait()
        async with self.writer_lock:
            if not self.input.closed:
                self.session.record("close_stdin", self.command_id)
                await self.session.driver.close_stdin()
                self.input = replace(self.input, closed=True)

    async def expect(
        self, pattern: bytes, stream: MatchStream = "stdout", timeout: float | None = None
    ) -> bytes:
        """Observe a bounded literal prompt, including split and newline-free prompts.

        :param pattern: Nonempty literal bytes fitting the matching window.
        :param stream: stdout, stderr, or either independent stream.
        :param timeout: Independent observation timeout in seconds.
        :returns: Matched bytes.
        :raises InputError: Output ended before the prompt appeared.
        :raises TimeoutError: The observation deadline expired.
        """
        self.session.record("expect", self.command_id, pattern, stream)
        return await self.hub.expect(pattern, stream, timeout)

    def events(self) -> AsyncIterator[OutputEvent]:
        """Subscribe to future output independently of primary capture.

        :returns: Bounded asynchronous event subscription.
        """
        return self.hub.events()

    async def emit(self, stream: StreamName, data: bytes) -> None:
        """Capture bytes before notifying observers.

        :param stream: Source transport.
        :param data: Raw bounded chunk.
        """
        await self.captures[stream].feed(data)
        self.hub.publish(stream, data)

    def snapshot(self) -> CommandSnapshot:
        """Read command state without executing another shell command.

        :returns: Immutable current command view.
        """
        return CommandSnapshot(
            self.command_id,
            self.state,
            self.captures["stdout"].received,
            self.captures["stderr"].received,
            self.result,
        )
