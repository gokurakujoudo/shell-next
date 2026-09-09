"""Private pipe, manifest, and wrapper preparation for native commands."""

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from shell_next.backends.native.channels import CommandChannel
from shell_next.backends.native.syntax import command_wrapper, invocation, source_script
from shell_next.models.commands import ProcessCommand
from shell_next.models.state import Backend

if TYPE_CHECKING:
    from shell_next.backends.native.driver import NativeDriver
    from shell_next.frontend.handle import CommandHandle


async def prepare_command(driver: NativeDriver, handle: CommandHandle) -> None:
    """Allocate only the current command's native transport resources.

    :param driver: Resource-owning native driver.
    :param handle: Command with a validated identity request.
    :raises OSError: Pipe or private manifest creation fails.
    """
    driver.ready.clear()
    backend = driver.config.backend
    token = handle.command_id
    privilege = handle.options.privilege
    elevated = privilege.requirement == "elevated"
    names = ["stdout", "stderr", "stdin"]
    if elevated and privilege.interactive:
        names.extend(("auth_out", "auth_in"))
    for name in names:
        path = (
            rf"\\.\pipe\shell-next-{token}-{name}"
            if os.name == "nt"
            else str(driver.native.path / f"{token}.{name}")
        )
        driver.channels[name] = CommandChannel(path, name in ("stdin", "auth_in"))
        await driver.channels[name].open()
    paths = {name: channel.path for name, channel in driver.channels.items()}
    suffix = {Backend.BASH: ".sh", Backend.POWERSHELL: ".ps1", Backend.CMD: ".cmd"}[backend]
    native_script = not isinstance(handle.command, ProcessCommand)
    if isinstance(handle.command, ProcessCommand):
        argv = [handle.command.executable, *handle.command.args]
    else:
        script = driver.native.path / f"{token}.user{suffix}"
        driver.files.append(script)
        script.write_text(handle.command.text + "\n", encoding="utf-8")
        text = source_script(script, backend)
        argv = [
            driver.config.executable or "bash",
            "--noprofile",
            "--norc",
            "-c",
            handle.command.text,
        ]
    if not native_script or elevated:
        manifest = driver.native.path / f"{token}.json"
        driver.files.append(manifest)
        manifest.write_text(
            json.dumps(
                {
                    **paths,
                    "argv": argv,
                    "token": token,
                    "elevated": elevated,
                    "interactive": privilege.interactive,
                    "target": privilege.target_identity,
                    "attempts": privilege.attempts,
                }
            ),
            encoding="utf-8",
        )
        text = invocation(
            [sys.executable, str(Path(__file__).with_name("bridge.py")), str(manifest)], backend
        )
    wrapper = driver.native.path / f"{token}{suffix}"
    driver.files.append(wrapper)
    wrapper.write_text(
        command_wrapper(backend, text, token, native_script and not elevated, paths),
        encoding="utf-8",
    )
