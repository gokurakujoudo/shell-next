# Testing with mocks

Let application code accept a `SessionConfig` and use `use_shell_session`.
Tests replace only the implementation injection field:

```python
from shell_next import (
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
)

command = ProcessCommand("git", ("status", "--short"))
scenario = MockScenario([MockExpectation(command, (Emit(b" M README.md\n"),))])
config = SessionConfig(_session_cls=MockShellSession.configured(scenario))
# Pass config into the same application function used in production.
```

Use `Receive` to expect input, `Emit` for output, `Advance` for virtual time,
and `Failure` for failure scenarios. The mock does not interpret shell syntax;
declare simulated cwd/environment changes on the expectation.

Scenarios are strict by default. Unexpected commands and input fail, and unused
required expectations fail at normal session exit. `assert_called()` and
`assert_consumed()` provide explicit checks. Sensitive input is redacted from
call history when marked `secret=True`; privilege authentication is always redacted.

Ordinary mock execution creates no subprocesses, pipes, capture files, network
connections, or real sleeps, and does not mutate the parent environment or cwd.

See the [runnable application-test example](https://gokurakujoudo.github.io/shell-next/testing/).
