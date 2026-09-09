import asyncio

import pytest

from shell_next import (
    CommandOptions,
    ConcurrencyPolicy,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    Receive,
    SessionConfig,
    StdinMode,
    TimeoutPolicy,
    use_shell_session,
)


async def test_sixty_second_observation_timeout_never_waits_real_time() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario([MockExpectation(command, (Receive(b"go\n"),))])
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        async with asyncio.timeout(1):
            with pytest.raises(TimeoutError):
                await handle.wait(wait_timeout=60)
            with pytest.raises(TimeoutError):
                await handle.expect(b"missing", timeout=60)
        assert not handle.future.done()
        await handle.sendline(b"go")
        assert (await handle.wait(wait_timeout=60)).success
        assert (await handle.wait(wait_timeout=60)).success


async def test_finite_virtual_acquisition_and_queued_observation_are_immediate() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario(
        [
            MockExpectation(command, (Receive(b"go\n"),)),
            MockExpectation(command),
            MockExpectation(command),
        ]
    )
    config = SessionConfig(
        concurrency=ConcurrencyPolicy.QUEUE, _session_cls=MockShellSession.configured(scenario)
    )
    async with use_shell_session(config) as shell:
        first = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await first.ready.wait()
        second = shell.submit(command)
        async with asyncio.timeout(1):
            with pytest.raises(TimeoutError):
                await second.wait(wait_timeout=60)
            await second.stop()
            third = shell.submit(
                command, options=CommandOptions(timeouts=TimeoutPolicy(acquire=60))
            )
            assert not (await third.wait()).success
        await first.sendline(b"go")
        assert (await first.wait()).success


async def test_finite_virtual_wait_allows_ready_work_and_chunked_input() -> None:
    command = ProcessCommand("virtual")
    data = b"x" * 150000
    scenario = MockScenario(
        [MockExpectation(command, (Receive(data[:2]), Receive(data[2:]), Emit(b"done")))]
    )
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=CommandOptions(stdin=StdinMode.MANUAL))
        await handle.send(data)
        result = await handle.wait(wait_timeout=60)
        assert result.input.submitted == len(data)
        assert result.stdout.tail == b"done"
