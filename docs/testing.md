# Testing applications

Application functions should accept a `SessionConfig` and create sessions using
`use_shell_session`. Tests can then inject the official mock without introducing
a separate application execution path.

```python
import asyncio

from shell_next import (
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)


async def read_status(config: SessionConfig) -> bytes:
    async with use_shell_session(config) as shell:
        result = await shell.run(ProcessCommand("git", ("status", "--short")), check=True)
        return result.stdout.tail


async def test_status() -> None:
    command = ProcessCommand("git", ("status", "--short"))
    scenario = MockScenario([MockExpectation(command, (Emit(b" M README.md\n"),))])
    config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
    assert await read_status(config) == b" M README.md\n"
    scenario.assert_called(command)
    scenario.assert_consumed()


asyncio.run(test_status())
```

## Declare the interaction

| Scenario step | Meaning |
| --- | --- |
| `Emit(data, stream="stdout")` | Emit raw output to capture and observers. |
| `Receive(data)` | Expect bytes across transport chunk boundaries. |
| `Receive(None)` | Expect business stdin to close. |
| `Advance(seconds)` | Advance virtual command time without sleeping. |
| `Failure(kind)` | Simulate input, output, startup, or session failure. |

Use `MockExpectation.cwd` and `env` for simulated script state changes. The mock
does not parse Bash, PowerShell, or cmd syntax. Authentication fields can model
private password prompts, cached credentials, or rejected authentication.

## Keep tests strict

Unexpected commands raise `MockUnexpectedCommandError`; mismatched or extra
input raises `MockUnexpectedInputError`. Unused required command expectations
raise `MockExpectationNotConsumedError` on normal context exit. A body exception
remains the primary exception.

The mock uses the shared command lifecycle, queue, capture, and input frontend.
Ordinary scenarios create no subprocesses, pipes, network connections, capture
files, or real sleeps, and never change the parent cwd or environment.

`scenario.calls` records ordered observable operations. Mark sensitive business
input with `secret=True` to redact it; privilege authentication is always
redacted. Use [real backend tests](development/architecture.md) when verifying
OS-specific syntax or filesystem behavior.
