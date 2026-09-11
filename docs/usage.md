# Using shell-next

Use Python 3.14 or newer. Bash is supported on Linux, with RHEL 8 as the
reference system. Windows supports PowerShell 7 (`pwsh`) and cmd. Choose the
backend explicitly; PowerShell scripts and Bash scripts are different languages.

## Persistent sessions

```python
from shell_next import Backend, ProcessCommand, SessionConfig, SessionScript, use_shell_session


async def work(config: SessionConfig):
    async with use_shell_session(config) as shell:
        await shell.chdir("/srv/project")
        await shell.set_env("BUILD_MODE", "release")
        await shell.run(SessionScript("answer=42"), check=True)  # Bash syntax
        result = await shell.run(ProcessCommand("git", ("status", "--short")), check=True)
        return result.stdout_str()
```

`ProcessCommand` preserves argument boundaries, including shell metacharacters.
`SessionScript` executes trusted native code in the existing shell scope. The
`sn_` namespace and Bash descriptor 9 belong to the private session protocol.
Explicit shell termination or protocol damage invalidates the session.

`get_cwd()` and `get_env(name=None)` query the interpreter. `snapshot()` reads
cached state without executing a command, so native script changes may not yet
appear there. State queries require enough retained output for their JSON reply;
they raise `SessionProtocolError` if capture truncates it.

## Ownership, input, and deadlines

`run()` owns the command through cleanup. `command()` provides a scoped live
handle. `submit()` immediately returns a session-owned handle; leaving it
unobserved does not abandon capture or cleanup.

The default stdin mode closes business stdin. Use `StdinMode.MANUAL` to call
`send()`, `sendline()`, and `close_stdin()`. Use `StdinMode.PLAN` with an
`InputPlan` of `Expect`, `Send`, `SendLine`, and `CloseStdin` steps for automation.
One logical writer serializes submissions. Cancelled or failed input is never
retried, and the result records accepted and submitted byte counts separately.

```python
from shell_next import CommandOptions, Expect, InputPlan, SendLine, StdinMode, TimeoutPolicy

options = CommandOptions(
    stdin=StdinMode.PLAN,
    input_plan=InputPlan((Expect(b"Name: ", timeout=5), SendLine(b"Ada"))),
    timeouts=TimeoutPolicy(execution=30, acquire=5, drain=2),
)
```

Prompt matching is literal, bounded, and byte-oriented; newline-free prompts
and prompts split across reads work. `stream="either"` searches stdout and
stderr independently. Host prompts, terminals, and full-screen programs are
outside the first release's capabilities.

`handle.wait(wait_timeout=5)` limits that observation. Cancelling or timing out
the wait leaves the command running. Cancelling `run()`, exiting a command
context exceptionally, calling `stop()`, or reaching an execution deadline
initiates cleanup. Preparation, acquisition, soft stop, force stop, output drain,
and capture finalization have independent budgets. Forced interruption breaks
the session, with no automatic restart.

`ConcurrencyPolicy.REJECT` rejects a second submission immediately.
`ConcurrencyPolicy.QUEUE` serializes commands in FIFO order. A scoped command
owner cannot recursively acquire the same session. Separate sessions can run
concurrently.

## Results and capture

Use `result.outcome` for the lifecycle outcome and `result.success` for normalized
success. An ordinary nonzero exit still has outcome `EXITED`. PowerShell also
reports last-success, native exit code, and terminating-error status separately.
`check=True` raises a typed exception after the result is finalized; the exception
retains that result. Error classes are available from `shell_next.errors`.

`result.command` retains the exact submitted `ProcessCommand` (executable and
argument tuple) or `SessionScript` (including original whitespace), even on
failure or cancellation before execution. It contains no generated backend
wrapper and is excluded from the result's repr. The field defaults to `None`
only for compatibility with manually constructed legacy results.

`result.stdout_str(encoding="utf-8", errors="replace")` and
`result.stderr_str(encoding="utf-8", errors="replace")` decode the retained raw
tails. They preserve whitespace and never read capture files. An empty tail
returns an empty string. Replacement decoding tolerates malformed bytes and a
multibyte character cut by the tail boundary; use `errors="strict"` to raise
`UnicodeDecodeError`, or select another Python codec such as `encoding="cp1252"`.
Raw bytes and completeness accounting remain available on `stdout` and `stderr`.

Configure `SessionConfig(capture=CaptureConfig(tail_bytes=4096))` to keep the last
4,096 bytes independently for stdout and stderr. The default maximum is 65,536
bytes (64 KiB) per stream. Zero retains no tail, negative limits are rejected,
and output beyond the limit is still drained and counted. Tail truncation does
not by itself make execution unsuccessful. Full capture files and prompt windows
use their own existing policies.

<!-- python-doc-exec -->
```python
import asyncio

from shell_next import (
    CaptureConfig,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)


async def inspect_result():
    command = ProcessCommand("example", ("argument with spaces",))
    scenario = MockScenario(
        [
            MockExpectation(command, (Emit(b"prefix:done"), Emit(b"warning", "stderr"))),
        ]
    )
    config = SessionConfig(capture=CaptureConfig(tail_bytes=4))
    config._session_cls = MockShellSession.configured(scenario)
    async with use_shell_session(config) as shell:
        result = await shell.run(command)
    assert result.command is command
    assert result.stdout_str() == "done"
    assert result.stderr_str() == "ning"
    assert result.stdout.received == 11
    assert not result.stdout.complete


asyncio.run(inspect_result())
```

Stdout and stderr have independent results. Memory tails, prompt windows, and
subscriber queues are bounded. To preserve full output, set
`CaptureConfig(directory=existing_directory)`. Unique files are created without
overwriting existing files. `committed` counts bytes only after flush and fsync.
`complete`, `sealed`, `end`, and `unread_possible` distinguish truncation,
storage failure, and forced cleanup. Explicit discard still counts received bytes.

`handle.events()` observes future chunks. Slow subscribers receive
`OutputSubscriberError`; they cannot stop primary capture. Events include stream,
sequence, timestamp, and per-stream byte offset. They do not establish a global
ordering between independently produced stdout and stderr bytes.

## Diagnostic representations

`repr()` on public commands, configuration, input steps, results, snapshots,
capabilities, and mock scenarios shows the class name and named fields. Enum
values appear as names such as `Outcome.EXITED`. Long strings, byte payloads,
collections, and nested records are abbreviated with `...`; large byte previews
include the full byte count. Stored values and capture limits are unchanged.

Sessions show their identifier, backend, lifecycle state, and pending count.
Command handles show their identifier, state, stdout/stderr byte counts, and
whether the result is finalized. Repr reads in-memory state without executing
commands, waiting, reading files, or calling password providers.

Input payloads, password providers, configuration and snapshot environments,
mock environment updates, and the original command inside a result remain hidden.
Commands and output previews may still contain caller-supplied sensitive text;
repr is a diagnostic display, not a serialization or general-purpose redactor.

<!-- python-doc-exec -->
```python
from shell_next import OutputResult, ProcessCommand

command = ProcessCommand("git", ("status", "--short"))
assert repr(command) == "ProcessCommand(executable='git', args=('status', '--short'))"
output = OutputResult(received=1000, tail=b"x" * 1000, complete=False)
assert "(1000 bytes)" in repr(output)
assert "complete=False" in repr(output)
assert len(output.tail) == 1000
```

## Sudo

```python
from shell_next import CommandOptions, PrivilegeRequest


# Supply an application's asynchronous secret-store function, returning bytes.
def elevated_options(password_provider):
    return CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated",
            interactive=True,
            password_provider=password_provider,
            attempts=1,
        )
    )
```

Bash supports interactive and noninteractive sudo. Authentication uses private
channels and a unique prompt, independently of business stdin/stdout/stderr.
The provider is called only when sudo requests a password; a valid credential
cache needs no provider call. Passwords are absent from argv, results, and mock
history. Provider failures expose a generic authentication error.

An elevated `SessionScript` runs in a separate elevated Bash process, so its
state changes do not persist in the ordinary session. `target_identity` selects
the sudo target. Privileged descendants cannot be guaranteed contained after
changing identity: cleanup reports remain conservative, and `strict_cleanup=True`
is rejected before execution. Windows active elevation is unsupported.

## Application tests

Pass the same `SessionConfig` into production code and set only its injection
field in tests:

```python
from shell_next import Emit, MockExpectation, MockScenario, MockShellSession, ProcessCommand

scenario = MockScenario(
    [
        MockExpectation(ProcessCommand("git", ("status", "--short")), (Emit(b" M README.md\n"),)),
    ]
)
config._session_cls = MockShellSession.configured(scenario)
```

Mock scripts do not parse shell syntax. Declare state changes using an
expectation's `cwd` and `env` fields. `Receive` matches the input byte stream
across transport chunks; `Receive(None)` expects EOF. `Advance` changes virtual
time, and `Failure` injects input, output, startup, or session failures.
Authentication expectations can model prompts, cache hits, and rejection.

Strict scenarios reject unexpected commands and input, and reject unused command
expectations at normal context exit. `assert_called()` and `assert_consumed()`
support explicit assertions. Calls are recorded in order; use `secret=True` on
manual or planned input to redact payloads. The mock does not create processes,
network connections, capture files, or real sleeps, and never changes the Python
process's directory or environment.
