"""Persistent native interpreter startup and bounded containment shutdown."""

import asyncio
import os
import tempfile
from pathlib import Path

from shell_next.backends.bash.containment import PosixGroup
from shell_next.backends.native.containment import create_containment
from shell_next.backends.windows.containment import WindowsJob
from shell_next.errors import CapabilityError, SessionStartupError
from shell_next.models.config import SessionConfig
from shell_next.models.results import CleanupReport
from shell_next.models.state import Backend


class NativeProcess:
    """Own the interpreter, control pipe, private directory, and containment unit.

    :param config: Validated session startup configuration.
    """

    def __init__(self, config: SessionConfig) -> None:
        """Initialize ownership without creating a process or filesystem resource.

        :param config: Session startup configuration.
        """
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self.containment: PosixGroup | WindowsJob | None = None
        self.directory: tempfile.TemporaryDirectory[str] | None = None
        self.path = Path()
        self.errors: list[str] = []
        self.error_reader: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the selected shell and adopt it even if the calling task is cancelled.

        :raises CapabilityError: The selected backend does not run on this platform.
        :raises SessionStartupError: Startup or containment assignment fails.
        """
        backend = self.config.backend
        if (backend == Backend.BASH) == (os.name == "nt"):
            raise CapabilityError("Bash requires POSIX; PowerShell and cmd require Windows")
        self.directory = tempfile.TemporaryDirectory(prefix="shell-next-")
        self.path = Path(self.directory.name)
        executable = self.config.executable
        if backend == Backend.BASH:
            argv = [executable or "bash", "--noprofile", "--norc"]
        elif backend == Backend.POWERSHELL:
            driver = self.path / "driver.ps1"
            driver.write_text(
                "$sn_control = [Console]::In\n"
                "while ($null -ne ($sn_path = $sn_control.ReadLine())) { . $sn_path }\n",
                encoding="utf-8",
            )
            argv = [
                executable or "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(driver),
            ]
        else:
            argv = [executable or "cmd.exe", "/d", "/q", "/v:off"]
        environment = dict(os.environ)
        environment.update(self.config.env)
        creation = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
                env=environment,
                start_new_session=os.name != "nt",
                creationflags=0x08000200 if os.name == "nt" else 0,
            )
        )
        # Win32 CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP avoids interactive consoles.
        try:
            self.process = await asyncio.shield(creation)
            self.containment = create_containment(self.process)
            self.error_reader = asyncio.create_task(self.drain_control_errors())
            if backend == Backend.BASH:
                await self.write("exec 9>&1\n")
            elif backend == Backend.CMD:
                await self.write("chcp 65001 >nul\n")
        except BaseException as exc:
            if self.process is None and not creation.cancelled():
                try:
                    self.process = await creation
                except OSError:
                    pass
            await self.close()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise SessionStartupError(type(exc).__name__) from exc

    async def drain_control_errors(self) -> None:
        """Continuously drain protocol diagnostics, retaining only bounded error metadata."""
        assert self.process is not None and self.process.stderr is not None
        while data := await self.process.stderr.read(65536):
            if data:
                self.errors[:] = ["Native shell wrote to its private diagnostic channel"]

    async def write(self, text: str) -> None:
        """Submit trusted control text to the persistent shell.

        :param text: Native control text, not business input.
        :raises ConnectionError: The shell has lost its control pipe.
        """
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.write(text.encode("utf-8"))
        await self.process.stdin.drain()

    async def close(self) -> CleanupReport:
        """Terminate all contained descendants and release session resources.

        :returns: Cleanup evidence including secondary failures.
        """
        errors: list[str] = []
        if self.process is not None:
            try:
                if self.containment is not None:
                    self.containment.terminate()
                elif self.process.returncode is None:
                    self.process.kill()
                async with asyncio.timeout(self.config.shutdown_timeout):
                    await self.process.wait()
            except (OSError, TimeoutError) as exc:
                errors.append(type(exc).__name__)
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.error_reader is not None:
                self.error_reader.cancel()
                await asyncio.gather(self.error_reader, return_exceptions=True)
            if self.containment is not None:
                self.containment.close()
            self.process = None
        if self.directory is not None:
            try:
                self.directory.cleanup()
            except OSError as exc:
                errors.append(type(exc).__name__)
            self.directory = None
        return CleanupReport(forced=True, contained=not errors, errors=tuple(errors))
