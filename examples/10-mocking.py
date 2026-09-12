"""Test application output, dialogue, and failures without starting a shell."""

import asyncio

from shell_next import (
    Advance,
    CommandOptions,
    Emit,
    Expect,
    Failure,
    InputPlan,
    MockExpectation,
    MockScenario,
    MockShellSession,
    Outcome,
    ProcessCommand,
    Receive,
    SendLine,
    SessionConfig,
    StdinMode,
    TimeoutPolicy,
    use_shell_session,
)


async def version(config: SessionConfig) -> str:
    async with use_shell_session(config) as shell:
        result = await shell.run(ProcessCommand("tool", ("--version",)), check=True)
        return result.stdout_str().strip()


async def main() -> None:
    # 1. Inject the double into the same application entry point.
    command = ProcessCommand("tool", ("--version",))
    scenario = MockScenario([MockExpectation(command, (Emit(b"tool 1.0\n"),))])
    config = SessionConfig()
    config._session_cls = MockShellSession.configured(scenario)
    assert await version(config) == "tool 1.0"
    scenario.assert_called(command)
    scenario.assert_consumed()

    # 2. Declare prompts, input, and state changes; no shell language is parsed.
    command = ProcessCommand("configure")
    scenario = MockScenario(
        [
            MockExpectation(
                command,
                (Emit(b"Name: "), Receive(b"Ada\n"), Emit(b"saved")),
                env=(("DEMO_USER", "Ada"),),
            )
        ]
    )
    config = SessionConfig()
    config._session_cls = MockShellSession.configured(scenario)
    options = CommandOptions(
        stdin=StdinMode.PLAN,
        input_plan=InputPlan((Expect(b"Name: "), SendLine(b"Ada", secret=True))),
    )
    async with use_shell_session(config) as shell:
        assert (await shell.run(command, options=options, check=True)).stdout_str() == "Name: saved"
        assert await shell.get_env("DEMO_USER") == "Ada"
    assert "b'Ada\\n'" not in repr(scenario.calls)

    # 3. Test timeouts with virtual time and output failure without real sleeps.
    for steps, expected in (
        ((Advance(60),), Outcome.TIMEOUT),
        ((Failure("output"),), Outcome.OUTPUT_FAILURE),
    ):
        command = ProcessCommand("job")
        scenario = MockScenario([MockExpectation(command, steps)])
        config = SessionConfig(defaults=CommandOptions(timeouts=TimeoutPolicy(execution=5)))
        config._session_cls = MockShellSession.configured(scenario)
        async with use_shell_session(config) as shell:
            result = await shell.run(command)
            assert result.outcome == expected
            assert not result.success
    print("Mock examples passed without native commands")


if __name__ == "__main__":
    asyncio.run(main())
