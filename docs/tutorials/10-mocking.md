# Deterministic application tests

Run this chapter on any host with Python 3.14+; no backend executable is needed.
Mock scenarios use the same session factory and shared lifecycle as native code.

1. Keep application logic in `version(config)` and inject only
   `config._session_cls`. Match the command exactly and assert returned output,
   recorded submission, and complete consumption of the scenario.
2. Declare a prompt/input exchange and an environment change. Mocks do not parse
   scripts or run the named executable. `secret=True` redacts the input in call
   history; environment updates must be declared explicitly on the expectation.
3. Inject an execution deadline using `Advance(60)` and a separate output failure
   using `Failure('output')`. Virtual time never sleeps. Each case owns a fresh
   scenario and session, because termination may invalidate a session.

Strict scenarios reject unmatched commands, unexpected input, and unused required
expectations. `Receive(None)` models EOF; `cwd` models directory changes. Native
exit status can be supplied with `BackendStatus(code=...)`. Authentication prompt
counts and outcomes model sudo cache hits and rejection without real credentials.
Mocks create no native processes, capture files, network calls, or real sleeps.

## Full example

File: [`examples/10-mocking.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/10-mocking.py).

```console
python examples/10-mocking.py
```

<!-- python-doc-exec mock: 10-mocking.py -->
```python
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
```

[Tutorial contents](index.md)
