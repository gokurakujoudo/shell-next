"""Recommended session factory and common command ownership frontend."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from typing import Any

from shell_next.backends.native.driver import NativeDriver
from shell_next.backends.protocol import SessionDriver
from shell_next.errors import (
    SessionBrokenError,
    SessionBusyError,
    SessionClosedError,
    SessionReentrancyError,
)
from shell_next.frontend.execution import run_owned
from shell_next.frontend.handle import CommandHandle
from shell_next.frontend.operations import state_operation
from shell_next.models.capabilities import backend_capabilities
from shell_next.models.commands import Command, ProcessCommand, SessionScript
from shell_next.models.config import CommandOptions, SessionConfig
from shell_next.models.privilege import validate_privilege
from shell_next.models.results import CleanupReport, CommandResult, SessionSnapshot
from shell_next.models.state import ConcurrencyPolicy, SessionState


class ShellSession:
    """Common lifecycle frontend; applications construct it through use_shell_session.

    :param config: Session implementation and native backend configuration.
    """

    def __init__(self, config: SessionConfig) -> None:
        """Initialize ownership without creating any operating-system resources.

        :param config: Validated session configuration.
        """
        self.config = config
        self.virtual_time = False
        self.session_id = uuid.uuid4().hex
        self.state = SessionState.NEW
        self.capabilities = backend_capabilities(config.backend)
        self.driver: SessionDriver = NativeDriver(config)
        self.lease = asyncio.Lock()
        self.pending: dict[str, CommandHandle] = {}
        self.tasks: set[asyncio.Task[None]] = set()
        self.scopes: set[asyncio.Task[Any]] = set()
        self.cwd = config.cwd
        self.environment = dict(config.env)
        self.close_task: asyncio.Task[CleanupReport] | None = None

    def clock(self) -> float:
        """Read the native monotonic clock.

        :returns: Monotonic seconds, unrelated to wall-clock time.
        """
        return time.monotonic()

    def record(self, operation: str, *args: object) -> None:
        """Provide the mock observation hook; production retains no input history.

        :param operation: Observable operation name.
        :param args: Payload-safe operation arguments.
        """

    def next_command_id(self) -> str:
        """Allocate an unpredictable native command and control identifier.

        :returns: Unique hexadecimal command identifier.
        """
        return uuid.uuid4().hex

    async def __aenter__(self) -> ShellSession:
        """Start backend resources within the configured startup deadline.

        :returns: Active session.
        :raises SessionClosedError: This session has already been entered.
        """
        if self.state != SessionState.NEW:
            raise SessionClosedError("Sessions can be entered only once")
        try:
            async with asyncio.timeout(self.config.startup_timeout):
                await self.driver.start()
            self.state = SessionState.OPEN
            self.record("enter")
            return self
        except BaseException:
            await self.aclose()
            raise

    async def __aexit__(self, *exc: object) -> None:
        """Attempt shutdown while preserving an exception from the session body.

        :param exc: Python context-manager exception information.
        """
        await self.aclose()

    @property
    def is_usable(self) -> bool:
        """Report whether the session accepts another command.

        :returns: True only for an open, protocol-healthy session.
        """
        return self.state == SessionState.OPEN

    def submit(
        self,
        command: Command,
        *,
        options: CommandOptions | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> CommandHandle:
        """Register a command synchronously and schedule its owned execution.

        :param command: Structural process or native script.
        :param options: Complete command options, or session defaults.
        :param check: Optional result-check override.
        :param timeout: Optional execution timeout override in seconds.
        :returns: Managed handle, immediately owned by the session.
        :raises SessionBrokenError: The session protocol is broken.
        :raises SessionClosedError: The session is not open.
        :raises SessionBusyError: REJECT policy already owns a command.
        :raises SessionReentrancyError: A scoped owner would deadlock itself.
        :raises TypeError: The command is not an explicit command description.
        """
        self.validate_submission()
        if not isinstance(command, (ProcessCommand, SessionScript)):
            raise TypeError("Use ProcessCommand or SessionScript")
        resolved = options or self.config.defaults
        if check is not None:
            resolved = replace(resolved, check=check)
        if timeout is not None:
            resolved = replace(resolved, timeouts=replace(resolved.timeouts, execution=timeout))
        validate_privilege(resolved.privilege, self.capabilities)
        handle = CommandHandle(self, self.next_command_id(), command, resolved)
        handle.reservation = self.driver.reserve(command)
        self.pending[handle.command_id] = handle
        self.record("submit", command)
        task = asyncio.create_task(run_owned(handle))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return handle

    def validate_submission(self) -> None:
        """Validate lifecycle and ownership before submitting work or a mock state operation.

        :raises SessionBrokenError: The session was invalidated.
        :raises SessionClosedError: The session is not open.
        :raises SessionReentrancyError: This task already owns a scoped command.
        :raises SessionBusyError: Immediate rejection applies to an occupied session.
        """
        if self.state == SessionState.BROKEN:
            raise SessionBrokenError("The interrupted session cannot be reused")
        if not self.is_usable:
            raise SessionClosedError("Session is not open")
        if asyncio.current_task() in self.scopes:
            raise SessionReentrancyError("A scoped command already owns this session")
        if self.pending and self.config.concurrency == ConcurrencyPolicy.REJECT:
            raise SessionBusyError("Session already owns a command")

    async def run(
        self,
        command: Command,
        *,
        options: CommandOptions | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Own a command through finalization, stopping it if this owner is cancelled.

        :param command: Command description.
        :param options: Complete command options, or defaults.
        :param check: Optional unsuccessful-result exception conversion.
        :param timeout: Optional execution deadline in seconds.
        :returns: Final immutable command result.
        :raises asyncio.CancelledError: Owner cancellation, after cleanup is requested.
        """
        handle = self.submit(command, options=options, check=check, timeout=timeout)
        try:
            return await handle.wait()
        except asyncio.CancelledError:
            with suppress(Exception):
                await handle.stop()
            raise

    @asynccontextmanager
    async def command(
        self,
        command: Command,
        *,
        options: CommandOptions | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[CommandHandle]:
        """Own a live command until normal completion or exceptional context exit.

        :param command: Command description.
        :param options: Complete command options, or defaults.
        :param check: Optional unsuccessful-result exception conversion.
        :param timeout: Optional execution deadline in seconds.
        :returns: Asynchronous command context.
        """
        handle = self.submit(command, options=options, check=check, timeout=timeout)
        owner = asyncio.current_task()
        assert owner is not None
        self.scopes.add(owner)
        try:
            await handle.ready.wait()
            yield handle
            await handle.wait()
        except BaseException:
            with suppress(Exception):
                await handle.stop()
            raise
        finally:
            self.scopes.discard(owner)

    def snapshot(self) -> SessionSnapshot:
        """Inspect cached state without scheduling an implicit command.

        :returns: Immutable session snapshot; native-script state may be newer.
        """
        return SessionSnapshot(
            self.session_id,
            self.state,
            next(iter(self.pending), None),
            sum(h.state == "queued" for h in self.pending.values()),
            self.cwd,
            tuple(self.environment.items()),
        )

    async def chdir(self, path: str) -> None:
        """Change the persistent working directory.

        :param path: Backend-native directory path.
        """
        await state_operation(self, "chdir", path)

    async def set_env(self, name: str, value: str) -> None:
        """Set one exported variable in the persistent session.

        :param name: Environment variable name.
        :param value: Environment variable value.
        """
        await state_operation(self, "set_env", name, value)

    async def unset_env(self, name: str) -> None:
        """Remove one exported variable from the persistent session.

        :param name: Environment variable name.
        """
        await state_operation(self, "unset_env", name)

    async def get_cwd(self) -> str:
        """Query the current persistent working directory.

        :returns: Native absolute working directory.
        """
        return str(await state_operation(self, "get_cwd"))

    async def get_env(self, name: str | None = None) -> str | dict[str, str] | None:
        """Query one exported variable or the entire exported environment.

        :param name: Variable name, or None for the environment view.
        :returns: Variable value, None when missing, or a copied environment map.
        """
        return await state_operation(self, "get_env", name)

    async def ping(self) -> bool:
        """Verify an idle shell can complete a command.

        :returns: Whether the health command succeeded.
        """
        return (await self.run(SessionScript("echo shell-next"), timeout=5)).success

    async def shutdown(self) -> CleanupReport:
        """Prevent submissions, stop owned commands, and close the backend.

        :returns: Idempotently retained shutdown evidence.
        """
        self.state = SessionState.CLOSING
        for handle in tuple(self.pending.values()):
            handle.stop_requested.set()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        report = await self.driver.close()
        self.state = SessionState.CLOSED
        self.record("close")
        return report

    async def aclose(self) -> CleanupReport:
        """Idempotently close owned resources, independent of observer cancellation.

        :returns: Retained shutdown report.
        """
        if self.close_task is None:
            self.close_task = asyncio.create_task(self.shutdown())
        return await asyncio.shield(self.close_task)


@asynccontextmanager
async def use_shell_session(config: SessionConfig) -> AsyncIterator[ShellSession]:
    """Create the configured implementation and always attempt session shutdown.

    :param config: Session setup; _session_cls supplies test injection.
    :returns: Asynchronous context yielding the active session interface.
    """
    implementation = config._session_cls or ShellSession
    async with implementation(config) as session:
        yield session
