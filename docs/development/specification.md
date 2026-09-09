# shell-next Development Specification

## 1. The package provides one asynchronous Shell session abstraction across three backends.

`shell-next` is a Python 3.14 package that provides a unified asynchronous interface for managing persistent Shell sessions and executing commands through Bash, PowerShell, and Windows Command Prompt.

The first release supports Bash on RHEL 8 as the reference backend, PowerShell 7 on Windows as the primary Windows backend, and `cmd.exe` on Windows as a compatibility backend.

A Shell session represents one persistent operating-system Shell process that may remain idle between commands and may preserve supported Shell state across commands. The package does not create a new Shell process for every command unless an individual backend explicitly requires an isolated process for a specific operation.

Different sessions may run concurrently, but one session executes at most one stateful command at a time. This restriction ensures that current directories, environment variables, Shell variables, functions, aliases, and other backend-specific session state have deterministic ordering.

The package unifies session lifecycle, command lifecycle, timeout handling, input handling, output capture, result reporting, cancellation, testing, and capability discovery. It does not attempt to translate Bash, PowerShell, and cmd scripting languages into one another.

---

## 2. All downstream applications should create sessions through `use_shell_session(config)`.

The recommended entry point is:

```python
async with use_shell_session(config) as shell:
    ...
```

`use_shell_session(config)` creates the configured session implementation, enters it asynchronously, yields the active session, and guarantees that session shutdown is attempted when the outer context exits.

Downstream applications should not instantiate the production session implementation directly. This requirement preserves dependency injection and allows the same application code to run with `MockShellSession` during unit tests.

The `SessionConfig` object defines the selected backend, the initial working directory, the initial environment, default command options, output capture settings, concurrency policy, startup and shutdown timeouts, privilege configuration, and the session implementation class.

The following assignment is the official test injection mechanism:

```python
config._session_cls = MockShellSession
```

When this value is set, the same call:

```python
async with use_shell_session(config) as shell:
    ...
```

must create a `MockShellSession` instead of starting a real Shell.

The `_session_cls` field is an implementation injection point and must not affect configuration serialization, logging, equality, environment propagation, or subprocess creation.

---

## 3. Each session exposes one consistent public interface.

An active session exposes the following operations.

| Interface | Contract |
|---|---|
| `await shell.run(command, ...)` | This operation executes one command through the current session, automatically manages its complete lifecycle, and returns a final `CommandResult`. |
| `async with shell.command(command, ...) as cmd` | This operation starts one command and gives the caller explicit access to its live input, output, waiting, and stopping interfaces until the inner context exits. |
| `shell.submit(command, ...)` | This operation synchronously submits a command to the session and immediately returns a managed command handle without waiting for completion. |
| `await shell.chdir(path)` | This operation changes the persistent current directory of the session using backend-native semantics. |
| `await shell.set_env(name, value)` | This operation sets an environment variable in the persistent session state. |
| `await shell.unset_env(name)` | This operation removes an environment variable from the persistent session state. |
| `await shell.get_cwd()` | This operation returns the session's current working directory. |
| `await shell.get_env(name=None)` | This operation returns one environment variable or the session environment view. |
| `await shell.ping()` | This operation verifies that an idle session is healthy and able to accept another command. |
| `shell.snapshot()` | This operation returns an in-memory snapshot of the current session state without running an implicit user command. |
| `shell.capabilities` | This property describes the runtime capabilities of the selected backend. |
| `shell.is_usable` | This property reports whether the current session can accept additional commands. |
| `await shell.aclose()` | This operation performs an idempotent session shutdown and returns a shutdown report. |

The outer `async with` owns the Shell process and all commands submitted through that session. No submitted command may outlive the session without an explicit future feature that defines such ownership separately.

---

## 4. Commands are represented as either structured processes or backend-native scripts.

`ProcessCommand` represents an external executable plus an ordered argument list.

It should be the preferred command type for portable application logic because arguments are passed structurally rather than interpolated into Shell text. A `ProcessCommand` inherits the current session working directory and exported environment, but it does not depend on Shell-local variables, Shell functions, or Shell aliases.

`SessionScript` represents script text written in the native language of the selected backend.

A Bash `SessionScript` executes in the current Bash state space, a PowerShell `SessionScript` executes in the current PowerShell session scope, and a cmd `SessionScript` executes using cmd-compatible batch semantics.

A `SessionScript` may modify persistent session state. Such modifications are not rolled back when the script later fails.

The package does not convert Bash syntax to PowerShell syntax, PowerShell syntax to cmd syntax, or any other Shell language automatically.

Portable application logic should therefore prefer `ProcessCommand`, `shell.chdir()`, `shell.set_env()`, and `shell.unset_env()` whenever Shell-specific syntax is unnecessary.

---

## 5. A command can be executed in automatic, scoped, or submitted mode.

`await shell.run(...)` is the fully managed interface. It acquires the session execution lease, prepares the command, runs configured input automation, continuously captures output, applies execution deadlines, performs cleanup, finalizes the result, applies `check=True` if requested, and finally releases the session.

`async with shell.command(...) as cmd` is the interactive lifecycle interface. Entering the context starts and reliably adopts the command but does not wait for it to finish. The caller may then inspect output, wait for prompts, send input, close stdin, stop the command, or wait for completion.

When the inner command context exits normally while the command is still running, the default behavior is to wait for the command to complete. When the inner context exits because of an exception or cancellation, the package requests command termination, performs bounded cleanup, preserves the original Python exception, and then propagates that exception.

`shell.submit(...)` immediately registers a command with the session and returns a command handle. The command may begin immediately or may remain queued when queueing is enabled. The session retains ownership of the command even when the caller does not immediately await the returned handle.

Calling an asynchronous function without awaiting or scheduling it is not considered submission. Only `submit()` provides the explicit “start now, await later” contract.

---

## 6. One session always serializes commands.

The default concurrency policy is `REJECT`.

Under this policy, submitting another command while the session already owns an active command raises `SessionBusyError`.

An optional `QUEUE` policy may allow multiple submitted commands to wait in first-in, first-out order. Even under this policy, only one command runs at a time.

The package must detect reentrant use that would otherwise deadlock, such as calling `await shell.run(...)` from inside an active `async with shell.command(...)` block on the same session.

Different session objects remain independent and may execute concurrently.

---

## 7. Every command supports an independent timeout and cleanup policy.

Each command may define an execution timeout. The execution timeout begins when the command enters the actual execution phase and includes authentication, interactive input waiting, and program execution.

The timeout configuration may also define separate limits for acquiring the session, preparing the command, attempting a soft stop, waiting after a forced stop, draining remaining output, and finalizing capture files and result metadata.

When the execution deadline expires, the command is marked as timed out, automatic input stops, and the backend begins its termination procedure.

The package first attempts a backend-specific soft stop when available. If the command remains active after the configured grace period, the backend performs a force stop.

Output collection remains active during termination for as long as the configured drain policy permits.

A command timeout does not mean that the API must return at the exact timeout instant. The timeout defines when termination begins, while bounded cleanup may continue afterward.

A separate `wait_timeout` limits only one caller's wait operation and must never alter the command's own execution lifecycle.

---

## 8. Forced termination may invalidate the current session.

A persistent Shell may be executing built-ins or modifying internal state at the moment a command is interrupted.

The package therefore does not promise that an arbitrarily interrupted Shell can always continue safely.

If a command requires forceful termination or if the backend cannot prove that the session protocol remains healthy, the session becomes `BROKEN`.

A broken session rejects new commands and reports `is_usable == False`.

The package must never silently create a replacement Shell and present it as the original session because local variables, functions, aliases, current directory, exported state, and partially completed side effects may have been lost.

The caller may explicitly create a new session after inspecting the previous command result.

---

## 9. Input handling supports closed, automatic, and manual modes.

Each command chooses one stdin mode.

The `closed` mode provides no business input and should be the default for noninteractive commands.

The `plan` mode executes a predefined ordered `InputPlan`.

The `manual` mode keeps command input available so that the caller may send data while the command runs.

An `InputPlan` supports sequential sends, line sends, prompt matching, and explicit stdin closure.

An `Expect` step matches a literal byte pattern against stdout, stderr, or either stream. Matching must support patterns split across read chunks and prompts that do not end with a newline.

Each matcher must use a bounded rolling window so that unbounded process output cannot produce unbounded matching memory.

The first release guarantees literal byte matching. Complex regular-expression matching is not part of the required first-release contract.

All input sources are serialized through one logical stdin writer. Automatic input and caller-provided manual input must never interleave unpredictably.

The package must report when input was accepted, partially submitted, fully submitted, aborted, or failed.

A successful input submission only means that the package completed its own transport step. It does not prove that the target program consumed or accepted the data.

The package must never automatically resend input after cancellation because the original data may already have been partially or fully delivered.

---

## 10. Output capture always remains independent from output consumers.

Every command may capture stdout and stderr independently.

The production default should preserve raw bytes, maintain a bounded in-memory tail, and optionally persist complete output to files.

Output capture must continue even when no caller is currently iterating over output events.

A slow output subscriber must not become the primary backpressure mechanism for the subprocess.

Each output event identifies the command, sequence number, transport stream, byte offset, raw data, monotonic timestamp, and persistence state.

The shared model supports `stdout`, `stderr`, and an optional `terminal` transport stream.

PowerShell may additionally attach a backend-specific logical stream label for information such as warning, verbose, debug, or information output. The common contract must not require Bash or cmd to produce such labels.

Output results must distinguish the number of bytes received, the number of bytes durably committed to the configured capture destination, the retained tail, the end condition, whether the stream is complete, whether capture was sealed successfully, and whether unread bytes may still have existed when cleanup ended.

The package must not claim that output is complete when capture was truncated, storage failed, forced closure occurred, or the configured drain deadline expired.

---

## 11. Output storage must remain bounded and failure-aware.

Production capture may use memory, files, both, or explicit discard mode.

Memory storage must always have a configured upper bound.

File persistence must not perform large blocking filesystem operations directly inside the event loop.

The production implementation may use a dedicated bounded executor for ordinary file writes, but that executor must be isolated from the application's default executor.

When output arrives faster than storage can persist it, the package may temporarily apply transport backpressure. Persistent overload must follow an explicit policy, such as stopping the command or truncating output while marking the result incomplete.

The package must never silently discard output while reporting complete capture.

`MockShellSession` must keep capture entirely in memory by default and must not create capture files unless a test explicitly requests a filesystem-specific integration scenario.

---

## 12. Command results separate execution outcome from backend-specific status.

Every command ends with one immutable `CommandResult`.

The result identifies the session, command, backend, command kind, overall outcome, success state, backend status, timing data, stdout result, stderr result, input summary, privilege report, cleanup report, accumulated secondary errors, user tags, and whether the session remained reusable.

The normalized outcome may represent normal exit, timeout, caller stop, startup failure, input failure, output failure, session loss, or internal execution failure.

A process exit code must remain separate from the package's normalized outcome.

For `ProcessCommand`, the normalized status code normally reflects the external process exit code.

For Bash `SessionScript`, the backend status reflects Bash command status.

For cmd `SessionScript`, the backend status reflects `ERRORLEVEL`.

PowerShell has more than one error and success concept, so the PowerShell backend must preserve backend-native details such as terminating error state, last success state, and last native exit code instead of pretending that every PowerShell result is equivalent to one POSIX integer.

`check=True` converts an already finalized unsuccessful result into a typed exception that carries that `CommandResult`.

`check=False` suppresses only this conversion. It does not disable timeout enforcement, cleanup, capture protection, input validation, or privilege checks.

---

## 13. Cancellation semantics depend on ownership.

Cancelling one `command.wait()` operation cancels only that caller's observation and does not stop the command.

Cancelling `shell.run()` requests termination because `run()` owns the command it created.

Allowing cancellation to escape from an inner `async with shell.command(...)` block also requests command termination because that context owns the command lifecycle.

Leaving an output event iterator stops only the subscription and does not stop the command.

Leaving the outer session context prevents new submissions, handles the active command according to the session close policy, cancels queued commands that have not started, performs bounded session cleanup, and returns or records a session close report.

Cancellation must never cause the package to lose ownership of an operating-system process that was successfully created.

---

## 14. Privilege handling is portable at the API level but backend-specific in capability.

The public interface uses `PrivilegeRequest` instead of a sudo-specific option type.

A privilege request states whether elevated execution is required, which target identity is requested when applicable, whether authentication may be interactive, whether strict privileged cleanup is required, and how many authentication attempts are allowed.

The package must expose privilege capability through `shell.capabilities` before execution.

### Bash supports interactive and noninteractive sudo in the first release.

The Bash backend on RHEL 8 must support noninteractive sudo and interactive password-based sudo as first-release features.

Interactive sudo must not send a password through a normal business stdin plan.

Authentication and business input must use separate phases.

The backend first performs a dedicated authentication phase using sudo's stdin password mechanism and a unique private prompt. If sudo already has valid cached credentials, the password provider is not called unnecessarily.

When sudo requests a password, the backend calls the configured asynchronous `PasswordProvider`, sends the password only through the authentication channel, and never records that secret in command text, arguments, event logs, input history, results, exceptions, tags, or object representations.

After authentication succeeds, the business command runs through noninteractive sudo so that any unexpected reauthentication requirement becomes an explicit privilege execution failure instead of consuming business stdin.

Interactive sudo may target root or another sudo-authorized user.

The Bash backend must distinguish support for executing a privileged command from support for strictly containing and forcefully terminating every privileged descendant.

If strict privileged cleanup is requested but the configured environment cannot guarantee it, execution must fail before starting with a capability error. The backend must never silently downgrade a strict cleanup request to best-effort behavior.

### Windows explicitly does not support active elevation in the first release.

PowerShell and cmd backends do not support `PrivilegeRequest(requirement="elevated")` in the first release.

Such a request must raise `PrivilegeUnsupportedError`.

The package must not launch UAC dialogs, automate UAC, call PowerShell `RunAs`, emulate sudo, or start an implicit privileged broker.

If the parent Python process already runs with an elevated Windows token, child Shell processes naturally inherit that token. This operating-system inheritance is not considered active privilege elevation by `shell-next`.

---

## 15. Capability discovery defines backend differences explicitly.

Every active session exposes immutable `SessionCapabilities`.

Capabilities report whether the backend supports persistent session state, portable working-directory management, portable environment management, Shell-local variables, functions, aliases, `SessionScript`, `ProcessCommand`, separate stdout and stderr, logical output streams, raw process bytes, sequential input, prompt matching, native stdin interaction, host-level prompt interaction, terminal mode, soft stop, force stop, process containment, session survival after interruption, privilege execution, interactive privilege authentication, and strict privileged cleanup.

Application code should make capability decisions through this object instead of directly testing the operating system or backend type.

Unsupported requested behavior must fail explicitly with a capability error.

---

## 16. The three real backends share one frontend but retain native semantics.

| Capability | Bash on RHEL 8 | PowerShell 7 on Windows | cmd on Windows |
|---|---|---|---|
| The backend provides a persistent Shell session. | Yes. | Yes. | Yes. |
| The backend preserves the current working directory across commands. | Yes. | Yes. | Yes. |
| The backend preserves environment changes across commands. | Yes. | Yes. | Yes. |
| The backend preserves Shell-local variables. | Yes. | Yes. | Only to the extent supported by cmd semantics. |
| The backend preserves Shell functions. | Yes. | Yes. | No equivalent first-class function model is provided. |
| The backend supports `ProcessCommand`. | Yes. | Yes. | Yes. |
| The backend supports `SessionScript`. | Yes. | Yes. | Yes. |
| The backend supports separate stdout and stderr capture. | Yes. | Yes. | Yes. |
| The backend supports automatic prompt matching on standard streams. | Yes. | Yes, for standard-stream interaction. | Yes. |
| The backend guarantees PowerShell Host prompt automation. | Not applicable. | No. | Not applicable. |
| The backend supports command execution timeouts. | Yes. | Yes. | Yes. |
| The backend supports forceful session cleanup. | Yes, through POSIX process-group semantics. | Yes, through Windows process-containment mechanisms. | Yes, through Windows process-containment mechanisms. |
| The backend guarantees that a force-stopped session remains reusable. | No. | No. | No. |
| The backend supports noninteractive sudo. | Yes. | No. | No. |
| The backend supports interactive sudo authentication. | Yes. | No. | No. |
| The backend supports active Windows elevation. | Not applicable. | No in the first release. | No in the first release. |

Bash is the reference backend and defines the most complete first-release behavior.

PowerShell is the primary Windows backend and should preserve PowerShell session state through native PowerShell semantics.

cmd is a compatibility backend for existing batch scripts, cmd-native syntax, and traditional Windows executable workflows.

---

## 17. `MockShellSession` is a first-class downstream testing interface.

`MockShellSession` implements the same session and command protocols as the production session.

It must not start subprocesses, open Bash, start PowerShell, start cmd, create FIFOs, create Named Pipes, create Job Objects, send signals, call sudo, modify `os.environ`, call `os.chdir()`, access the network, perform real sleeps, or write capture files by default.

Its working directory, environment, session state, commands, stdout, stderr, input, timeout behavior, privilege behavior, and cleanup state exist only in memory.

Tests configure it through:

```python
config._session_cls = MockShellSession
```

and then call production application code through the same normal entry point:

```python
async with use_shell_session(config) as shell:
    ...
```

No application code should require a separate “mock mode” branch.

---

## 18. Mock scenarios are deterministic and strict by default.

A `MockScenario` defines expected commands, expected input, emitted stdout and stderr, final command results, simulated session-state changes, simulated privilege behavior, and optional failure conditions.

Strict mode is the default.

When application code executes a command that has no matching expectation, the Mock raises `MockUnexpectedCommandError`.

When expected input does not match actual input, the Mock raises `MockUnexpectedInputError`.

When required expectations remain unused at the end of a strict test scenario, the Mock raises `MockExpectationNotConsumedError`.

A permissive mode may exist for exploratory tests, but production unit tests should normally use strict behavior.

---

## 19. The Mock supports real command-lifecycle semantics without real time.

The Mock must support `run()`, `command()`, `submit()`, `wait()`, `stop()`, `send()`, `sendline()`, `close_stdin()`, `expect()`, output events, command snapshots, session snapshots, capability discovery, cancellation, and result checking.

Interactive scenarios may emit prompts, wait for expected input, emit additional output, and then finish.

Mock timeouts use a virtual clock and must never require the test suite to sleep for the real timeout duration.

A test may therefore simulate a sixty-second execution timeout immediately and deterministically.

The Mock may simulate session invalidation after a forced stop, sudo authentication success or failure, unsupported privilege requests, output truncation, capture errors, and cleanup uncertainty.

Secret input must always be redacted from Mock call history just as it is from production logs.

---

## 20. The Mock records observable calls for assertions.

The Mock records session and command operations in deterministic order.

Tests may inspect calls such as session entry, directory changes, environment modifications, command execution, submission, prompt matching, input sends, stops, and session closure.

Secret values must never be stored verbatim in this call history.

The Mock should provide assertion helpers for verifying that expected commands were called, unexpected commands were not called, all required expectations were consumed, and no unexpected calls occurred.

The Mock itself should run through the same backend contract test suite wherever the common contract applies so that test behavior cannot silently diverge from production behavior.

---

## 21. The error model remains stable across all backends.

The public exception hierarchy distinguishes configuration errors, capability errors, session errors, command errors, input errors, capture errors, privilege errors, and Mock expectation errors.

Session errors include startup failure, busy-session errors, broken-session errors, closed-session errors, and session protocol errors.

Command errors include startup failure, non-success exit, timeout, caller stop, and interaction failure.

Privilege errors include unsupported privilege requests, authentication failure, execution failure, and insufficient cleanup capability.

Whenever a command reached a state where a final result could be produced, its exception should expose that `CommandResult`.

Secondary failures during output finalization or cleanup must be preserved in the result rather than replacing the primary reason that the command ended.

---

## 22. The first release should be developed in dependency order.

The project should first finalize the public API, common lifecycle state machines, result model, capability model, error model, `use_shell_session()`, and `MockShellSession`.

This first milestone allows downstream applications to integrate against a stable interface and write side-effect-free unit tests before any operating-system backend is complete.

The Bash backend should then implement the reference session protocol, process execution, stateful script execution, command-specific stdin/stdout/stderr channels, output capture, timeouts, cancellation, and process cleanup.

Interactive and noninteractive sudo must be completed before the first public release and are not deferred features.

The Windows platform layer should then implement reusable Windows process containment and command communication primitives.

The PowerShell backend should be implemented before the cmd backend because PowerShell is the primary Windows automation environment.

The cmd backend should complete first-release compatibility for legacy Windows scripts and cmd-native workflows.

---

## 23. The release must be validated against behavioral contracts rather than simple command execution.

The common contract tests must cover idle sessions, repeated commands, persistent working-directory changes, persistent environment changes, `run()`, `command()`, `submit()`, queue and reject policies, stdout and stderr capture, manual input, planned input, prompt matching, cancellation, timeout behavior, forced cleanup, session invalidation, output subscribers, and multiple concurrent sessions.

Bash integration tests must additionally cover stateful Bash scripts, functions, large simultaneous stdout and stderr, child processes, background descendants, ignored soft termination, interactive sudo, cached sudo credentials, wrong sudo passwords, privilege timeouts, business stdin after sudo authentication, and unverified privileged cleanup.

PowerShell integration tests must cover persistent PowerShell state, native process execution, script errors, stdout and stderr behavior, timeout, containment, forced session invalidation, and explicit rejection of privilege requests.

cmd integration tests must cover persistent directory and environment state, batch execution, `ERRORLEVEL`, native process execution, timeout, containment, forced session invalidation, and explicit rejection of privilege requests.

Mock tests must additionally verify that process count, process environment, process working directory, filesystem state, network state, and real elapsed time are unchanged by ordinary unit-test execution.

---

## 24. The first public release is complete only when the shared API behaves consistently across supported backends.

The package is ready for its first public PyPI release when the common API is stable, `MockShellSession` provides deterministic no-side-effect unit testing, Bash passes the complete reference contract including interactive sudo, PowerShell passes the common Windows contract, cmd passes the compatibility contract, timeout and cancellation races are covered, output capture remains bounded, and repeated session creation and destruction do not leak processes, file descriptors, handles, threads, tasks, or capture resources.

The public contract must remain centered on `use_shell_session(config)`, `run()`, `command()`, `submit()`, structured process execution, native session scripts, command-specific input and output handling, immutable results, explicit capabilities, and strict lifecycle ownership.

Backend-specific mechanisms remain implementation details, while backend-specific limitations remain explicit through capabilities and typed errors rather than hidden behavioral differences.

## 25. Quality

- Production class and function names must describe their purpose without an
  underscore prefix. Only Python protocol methods may use required dunder
  spellings. Avoid generic `internal` prefixes; curate exports with `__all__`.
- Ensure 100% test coverage with branch coverage.
- Each production Python file contains at most 200 code-bearing physical lines,
  excluding imports, docstrings, pure comments, and blank lines. Multiline
  signatures, expressions, and runtime strings count by their physical lines.
  Do not compress statements or move code into strings to evade the limit.
  Split modules by responsibility, using filenames that explain their contents.
- Every production docstring is English rST. Functions and methods document how
  they work, every parameter with `:param name:`, results with `:returns:` unless
  no value is returned, and intentional exceptions with `:raises Type:`.
  Useful special behavior may use an rST `.. note::`; do not add notes that
  merely restate ordinary lifecycle or ownership. Value classes document
  constructor fields and edge cases with the same conventions.
- Document every named constant and constant group, including enums, with its
  units (if any), source, purpose, and choice rationale. A coherent
  group may share its explanation. Do not invent external sources or annotate
  every ordinary control-flow literal. These production policies apply only to
  package source code; scripts and tests still follow Ruff and strict mypy.
- Unit tests mock external connectivity and isolate file input/output in a
  separate `TemporaryDirectory`.
- Runtime packages and tests follow `docs/development/architecture.md`. Tests mirror production subsystem boundaries; reusable fixtures live in dedicated support modules.
