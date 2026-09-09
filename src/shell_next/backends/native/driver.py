"""Command preparation and stream collection for persistent native interpreters."""

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from shell_next.backends.bash.password_channel import supply_passwords
from shell_next.backends.native.channels import CommandChannel
from shell_next.backends.native.preparation import prepare_command
from shell_next.backends.native.process import NativeProcess
from shell_next.backends.native.syntax import quote, source_script
from shell_next.backends.native.termination import stop_native
from shell_next.errors import CaptureError, SessionProtocolError
from shell_next.models.commands import Command
from shell_next.models.config import SessionConfig
from shell_next.models.privilege import PrivilegeReport
from shell_next.models.results import BackendStatus, CleanupReport
from shell_next.models.state import Backend

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle


class NativeDriver:
    """Transport implementation shared by the three native shell languages.

    :param config: Session configuration.
    """

    def __init__(self, config: SessionConfig) -> None:
        """Create resource bookkeeping without starting the interpreter.

        :param config: Validated session setup.
        """
        self.config = config
        self.native = NativeProcess(config)
        self.channels: dict[str, CommandChannel] = {}
        self.files: list[Path] = []
        self.pumps: list[asyncio.Task[None]] = []
        self.activation: asyncio.Task[None] | None = None
        self.ready = asyncio.Event()
        self.timeouts = config.defaults.timeouts
        self.authentication: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the interpreter and its containment unit.

        :raises SessionProtocolError: The configured interpreter cannot start.
        """
        await self.native.start()

    def reserve(self, command: Command) -> None:
        """Accept a validated command; native preparation occurs after lease acquisition.

        :param command: Submitted command description.
        """

    async def prepare(self, handle: CommandHandle) -> None:
        """Create private command pipes and native wrapper files.

        :param handle: Command owning these resources.
        :raises OSError: Pipe or private file creation fails.
        """
        self.timeouts = handle.options.timeouts
        await prepare_command(self, handle)

    async def activate(self, handle: CommandHandle) -> None:
        """Open caller input only after native command-specific channels exist.

        :param handle: Command receiving the readiness notification.
        """
        if os.name == "nt":
            await self.channels["stdin"].connected.wait()
        else:
            await self.ready.wait()
        for channel in self.channels.values():
            channel.release_keeper()
        handle.ready.set()

    async def pump(self, handle: CommandHandle, name: str) -> None:
        """Continuously drain one command stream independently of subscribers.

        :param handle: Owning command capture.
        :param name: stdout or stderr endpoint.
        """
        channel = self.channels[name]
        while data := await channel.read(65536):
            await handle.emit("stdout" if name == "stdout" else "stderr", data)

    async def execute(self, handle: CommandHandle) -> BackendStatus:
        """Execute the prepared wrapper and await status plus bounded stream EOF.

        :param handle: Command owning the current execution lease.
        :returns: Backend-native completion status.
        :raises SessionProtocolError: The shell loses its control channel.
        :raises TimeoutError: Descendant output exceeds the drain deadline.
        """
        self.pumps = [asyncio.create_task(self.pump(handle, name)) for name in ("stdout", "stderr")]
        self.activation = asyncio.create_task(self.activate(handle))
        if "auth_out" in self.channels:
            self.authentication = asyncio.create_task(
                supply_passwords(handle, self.channels["auth_out"], self.channels["auth_in"])
            )

            def authentication_finished(task: asyncio.Task[None]) -> None:
                """Stop execution if the secret provider fails.

                :param task: Completed private authentication task.
                """
                if not task.cancelled() and task.exception() is not None:
                    handle.stop_requested.set()

            self.authentication.add_done_callback(authentication_finished)
        wrapper = self.files[-1]
        line = (
            quote(str(wrapper), self.config.backend)
            if self.config.backend == Backend.POWERSHELL
            else source_script(wrapper, self.config.backend)
        )
        # PowerShell's driver accepts literal paths rather than expressions.
        if self.config.backend == Backend.POWERSHELL:
            line = str(wrapper)
        await self.native.write(line + "\n")
        process = self.native.process
        assert process is not None and process.stdout is not None
        token = (handle.command_id + ":").encode()
        while True:
            data = await self.native.read_control()
            if not data:
                raise SessionProtocolError(
                    "Persistent shell exited before reporting command status"
                )
            index = data.find(token)
            if index < 0:
                continue
            payload = data[index + len(token) :].strip()
            if payload == b"auth_ready":
                self.channels["auth_out"].release_keeper()
                self.channels["auth_in"].release_keeper()
                continue
            if payload.startswith(b"auth:"):
                _, authenticated, attempts = payload.split(b":")
                handle.privilege = PrivilegeReport(True, authenticated == b"1", int(attempts))
                continue
            if payload == b"ready":
                self.ready.set()
                continue
            if payload == b"startup_failure":
                handle.startup_failed = True
                continue
            if payload.startswith(b"{"):
                status = json.loads(payload)
                result = BackendStatus(
                    None, status["success"], status["native"], status["terminating"]
                )
            else:
                result = BackendStatus(int(payload))
            break
        handle.backend_status = result
        try:
            async with asyncio.timeout(handle.options.timeouts.drain):
                await asyncio.gather(*self.pumps)
        except TimeoutError as exc:
            raise CaptureError("Output drain deadline expired") from exc
        return result

    async def send(self, data: bytes) -> None:
        """Send business input on the active command's dedicated pipe.

        :param data: Input bytes, never shell control text.
        """
        await self.channels["stdin"].send(data)

    async def close_stdin(self) -> None:
        """Close only the active command's business input pipe."""
        self.channels["stdin"].close()

    async def finish(self) -> None:
        """Release per-command pipes, pump tasks, and private wrapper files."""
        tasks = [*self.pumps]
        if self.authentication is not None:
            tasks.append(self.authentication)
        if self.activation is not None:
            tasks.append(self.activation)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for channel in self.channels.values():
            channel.close()
        self.channels.clear()
        for path in self.files:
            path.unlink(missing_ok=True)
        self.files.clear()
        self.pumps.clear()
        self.activation = None
        self.authentication = None

    async def stop(self) -> CleanupReport:
        """Invalidate and terminate the persistent shell's entire containment unit.

        :returns: Process cleanup report.
        """
        return await stop_native(self)

    async def close(self) -> CleanupReport:
        """Close all session resources idempotently.

        :returns: Process containment cleanup report.
        """
        await self.finish()
        return await self.native.close()
