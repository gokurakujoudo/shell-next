"""Shared ownership, execution deadlines, and immutable result finalization."""

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from shell_next.errors import (
    CaptureError,
    InputError,
    MockExpectationError,
    PrivilegeAuthenticationError,
    SessionProtocolError,
)
from shell_next.frontend.finalization import finalize_output
from shell_next.frontend.lease import acquire_lease
from shell_next.models.commands import ProcessCommand
from shell_next.models.input import CloseStdin, Expect, SendLine
from shell_next.models.results import BackendStatus, CleanupReport, CommandResult
from shell_next.models.state import Outcome, SessionState, StdinMode

if TYPE_CHECKING:
    from shell_next.frontend.handle import CommandHandle


async def automate_input(handle: CommandHandle) -> None:
    """Run exactly one ordered input source, without retries after cancellation.

    :param handle: Command whose input options determine the source.
    :raises InputError: Input transport or matching fails.
    """
    await handle.ready.wait()
    if handle.options.stdin == StdinMode.CLOSED:
        await handle.close_stdin()
    elif handle.options.input_plan is not None:
        for step in handle.options.input_plan.steps:
            if isinstance(step, Expect):
                await handle.expect(step.pattern, step.stream, step.timeout)
            elif isinstance(step, CloseStdin):
                await handle.close_stdin()
            else:
                await handle.write_input(
                    step.data + (b"\n" if isinstance(step, SendLine) else b""), step.secret
                )


async def execute_owned(handle: CommandHandle) -> tuple[Outcome, BackendStatus]:
    """Race execution, automatic input failure, and explicit termination.

    :param handle: Active command owning its session's execution lease.
    :returns: Normalized completion reason and native status.
    :raises InputError: The automatic input source failed.
    :raises TimeoutError: The command's execution deadline expired.
    """
    execution = asyncio.create_task(handle.session.driver.execute(handle))
    automation = asyncio.create_task(automate_input(handle))
    stopped = asyncio.create_task(handle.stop_requested.wait())
    tasks = [execution, automation, stopped]
    try:
        deadline = None if handle.session.virtual_time else handle.options.timeouts.execution
        async with asyncio.timeout(deadline):
            while True:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                if stopped in done:
                    outcome = Outcome.STARTUP_FAILURE if handle.startup_failed else Outcome.STOPPED
                    return outcome, BackendStatus()
                if automation in done:
                    try:
                        await automation
                    except MockExpectationError:
                        raise
                    except Exception as exc:
                        raise InputError("Automatic input failed") from exc
                    tasks.remove(automation)
                if execution in done:
                    status = await execution
                    handle.state = "finishing"
                    handle.hub.finish()
                    try:
                        async with asyncio.timeout(handle.options.timeouts.drain):
                            await automation
                    except MockExpectationError:
                        raise
                    except Exception as exc:
                        raise InputError("Command ended before its input plan completed") from exc
                    return Outcome.EXITED, status
    finally:
        for task in (execution, automation, stopped):
            task.cancel()
        await asyncio.gather(execution, automation, stopped, return_exceptions=True)


async def run_owned(handle: CommandHandle) -> None:
    """Acquire one lease, execute, finalize, and resolve one session-owned command.

    :param handle: Immediately registered submitted command.
    """
    session = handle.session
    outcome = Outcome.STOPPED
    status = BackendStatus()
    cleanup = CleanupReport()
    started: float | None = None
    errors: list[str] = []
    acquired = False
    forced = False
    expectation: MockExpectationError | None = None
    try:
        acquired = await acquire_lease(handle)
        if acquired and not handle.stop_requested.is_set() and session.state == SessionState.OPEN:
            handle.state = "preparing"
            async with asyncio.timeout(handle.options.timeouts.prepare):
                await session.driver.prepare(handle)
            handle.state = "running"
            started = session.clock()
            outcome, status = await execute_owned(handle)
    except TimeoutError:
        outcome = Outcome.TIMEOUT
    except InputError:
        outcome = Outcome.INPUT_FAILURE
    except CaptureError:
        outcome = Outcome.OUTPUT_FAILURE
        status = handle.backend_status
    except MockExpectationError as exc:
        expectation = exc
        outcome = Outcome.INPUT_FAILURE
    except SessionProtocolError:
        outcome = Outcome.SESSION_LOST
    except PrivilegeAuthenticationError:
        outcome = Outcome.STARTUP_FAILURE
    except OSError as exc:
        outcome = Outcome.STARTUP_FAILURE
        errors.append(type(exc).__name__)
    except Exception as exc:
        outcome = Outcome.INTERNAL_FAILURE
        errors.append(type(exc).__name__)
    finally:
        if acquired:
            if outcome != Outcome.EXITED and handle.state != "queued":
                forced = True
                session.state = SessionState.BROKEN
                try:
                    cleanup = await session.driver.stop()
                except Exception as exc:
                    errors.append(type(exc).__name__)
                    cleanup = CleanupReport(forced=True, contained=False)
            try:
                await session.driver.finish()
            except Exception as exc:
                errors.append(type(exc).__name__)
        handle.ready.set()
        stdout, stderr = await finalize_output(handle, forced)
        if handle.privilege.requested:
            cleanup = replace(cleanup, contained=False)
        errors.extend(
            f"{name}: {capture.error}"
            for name, capture in handle.captures.items()
            if capture.error is not None
        )
        if outcome == Outcome.EXITED and (not stdout.sealed or not stderr.sealed):
            outcome = Outcome.OUTPUT_FAILURE
        if outcome == Outcome.EXITED and handle.startup_failed:
            outcome = Outcome.STARTUP_FAILURE
        if (
            outcome == Outcome.EXITED
            and handle.privilege.requested
            and not handle.privilege.authenticated
        ):
            outcome = Outcome.STARTUP_FAILURE
        success = outcome == Outcome.EXITED and (
            status.last_success is True if status.last_success is not None else status.code == 0
        )
        result = CommandResult(
            session.session_id,
            handle.command_id,
            session.config.backend,
            "process" if isinstance(handle.command, ProcessCommand) else "script",
            outcome,
            success,
            status,
            started,
            session.clock(),
            stdout,
            stderr,
            handle.input,
            privilege=handle.privilege,
            cleanup=cleanup,
            secondary_errors=tuple(errors),
            tags=tuple(handle.options.tags.items()),
            session_reusable=session.state == SessionState.OPEN,
        )
        handle.result = result
        handle.state = "finished"
        handle.hub.finish()
        if expectation is not None:
            handle.future.set_exception(expectation)
        else:
            handle.future.set_result(result)
        if acquired:
            session.lease.release()
        session.pending.pop(handle.command_id, None)
