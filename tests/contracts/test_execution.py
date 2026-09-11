import asyncio
from pathlib import Path

import pytest

from shell_next import (
    BackendStatus,
    CaptureConfig,
    CommandOptions,
    ConcurrencyPolicy,
    Emit,
    Expect,
    InputPlan,
    MockExpectation,
    Receive,
    SendLine,
    StdinMode,
    use_shell_session,
)
from shell_next.errors import CommandFailedError, SessionBusyError, SessionReentrancyError
from tests.support.sessions import BACKENDS, config_for, python_command


@pytest.mark.parametrize("backend", BACKENDS)
async def test_repeated_raw_structural_commands(backend: str, directory: Path) -> None:
    command = python_command(
        "import os,sys; os.write(1,sys.argv[1].encode()); os.write(2,b'error')",
        'a" & $x %x% !x! 中文',
    )
    output = 'a" & $x %x% !x! 中文'.encode()
    expectation = MockExpectation(command, (Emit(output), Emit(b"error", "stderr")))
    async with use_shell_session(config_for(backend, directory, expectation, expectation)) as shell:
        for _ in range(2):
            result = await shell.run(command, check=True, timeout=10)
            assert result.command is command
            assert result.stdout_str() == output.decode("utf-8")
            assert result.stderr_str() == "error"
            assert result.stdout.tail == output
            assert result.stderr.tail == b"error"
            assert result.stdout.complete and result.session_reusable
        assert shell.snapshot().active_command is None


@pytest.mark.parametrize("backend", BACKENDS)
async def test_manual_input_rejection_and_reentrancy(backend: str, directory: Path) -> None:
    command = python_command(
        "import sys; sys.stdout.write('Name: '); sys.stdout.flush(); print(input())"
    )
    expected = MockExpectation(
        command, (Emit(b"Na"), Emit(b"me: "), Receive(b"Ada\n"), Emit(b"Ada\n"))
    )
    async with use_shell_session(config_for(backend, directory, expected)) as shell:
        async with shell.command(
            command, options=CommandOptions(stdin=StdinMode.MANUAL), timeout=10
        ) as handle:
            assert await handle.expect(b"Name: ") == b"Name: "
            with pytest.raises(SessionReentrancyError):
                await shell.run(command)
            await handle.sendline(b"Ada")
            result = await handle.wait()
            assert b"Ada" in result.stdout.tail
            assert result.input.submitted == 4
            assert handle.snapshot().result is result


@pytest.mark.parametrize("backend", BACKENDS)
async def test_planned_input_and_separate_wait_timeout(backend: str, directory: Path) -> None:
    command = python_command(
        "import sys; sys.stdout.write('ready'); sys.stdout.flush(); print(input())"
    )
    expectation = MockExpectation(
        command, (Emit(b"ready"), Receive(b"answer\n"), Emit(b"answer\n"))
    )
    plan = InputPlan((Expect(b"ready"), SendLine(b"answer")))
    async with use_shell_session(config_for(backend, directory, expectation)) as shell:
        result = await shell.run(
            command, options=CommandOptions(stdin=StdinMode.PLAN, input_plan=plan), timeout=10
        )
        assert result.success
        assert b"answer" in result.stdout.tail


@pytest.mark.parametrize("backend", BACKENDS)
async def test_submit_reject_and_cancelled_observation(backend: str, directory: Path) -> None:
    command = python_command("print(input())")
    expected = MockExpectation(command, (Receive(b"go\n"), Emit(b"go\n")))
    async with use_shell_session(config_for(backend, directory, expected)) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL), timeout=10)
        with pytest.raises(SessionBusyError):
            shell.submit(command)
        await handle.ready.wait()
        waiter = asyncio.create_task(handle.wait())
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        with pytest.raises(TimeoutError):
            await handle.wait(wait_timeout=0)
        assert not handle.future.done()
        await handle.sendline(b"go")
        assert (await handle.wait()).success


@pytest.mark.parametrize("backend", BACKENDS)
async def test_fifo_queue(backend: str, directory: Path) -> None:
    first = python_command("print(input())")
    second = python_command("print('second')")
    config = config_for(
        backend,
        directory,
        MockExpectation(first, (Receive(b"first\n"), Emit(b"first\n"))),
        MockExpectation(second, (Emit(b"second\n"),)),
    )
    config.concurrency = ConcurrencyPolicy.QUEUE
    async with use_shell_session(config) as shell:
        one = shell.submit(first, options=CommandOptions(stdin=StdinMode.MANUAL), timeout=10)
        two = shell.submit(second, timeout=10)
        await one.ready.wait()
        assert two.snapshot().state == "queued"
        await one.sendline(b"first")
        assert (await one.wait()).success
        assert (await two.wait()).stdout.tail.strip() == b"second"


@pytest.mark.parametrize("backend", BACKENDS)
async def test_checked_result_is_finalized(backend: str, directory: Path) -> None:
    command = python_command("import sys; print('before'); sys.exit(7)")
    expected = MockExpectation(command, (Emit(b"before\n"),), BackendStatus(7))
    async with use_shell_session(config_for(backend, directory, expected)) as shell:
        with pytest.raises(CommandFailedError) as failure:
            await shell.run(command, check=True, timeout=10)
        assert failure.value.result.stdout.tail.strip() == b"before"
        assert failure.value.result.status.code == 7
        assert failure.value.result.stdout.sealed
        assert failure.value.result.command is command
        assert shell.is_usable


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("tail_bytes", [None, 0, 1024, 200000, 200001])
async def test_bounded_capture_without_subscribers(
    backend: str, directory: Path, tail_bytes: int | None
) -> None:
    command = python_command("import os; os.write(1,b'a'*200000); os.write(2,b'b'*200000)")
    expected = MockExpectation(command, (Emit(b"a" * 200000), Emit(b"b" * 200000, "stderr")))
    config = config_for(backend, directory, expected)
    config.capture = CaptureConfig() if tail_bytes is None else CaptureConfig(tail_bytes=tail_bytes)
    limit = 65536 if tail_bytes is None else tail_bytes
    async with use_shell_session(config) as shell:
        result = await shell.run(command, timeout=10)
        assert result.success
        for stream, value in ((result.stdout, b"a"), (result.stderr, b"b")):
            assert stream.received == 200000
            assert stream.tail == value * min(limit, 200000)
            assert stream.complete == (limit >= 200000)
            assert stream.end == ("eof" if limit >= 200000 else "truncated")
