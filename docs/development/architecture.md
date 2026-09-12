# Architecture

The public entry point is `use_shell_session(SessionConfig(...))`. The factory
selects the implementation before entering the session, including the official
`config._session_cls` injection point. Application code should depend on this
interface instead of constructing native adapters.

## Dependency boundaries

| Responsibility | Modules | Tests |
| --- | --- | --- |
| Value validation and immutable contracts | `models/{commands,config,capabilities,state,results,input,privilege}`; `errors` | `tests/models` |
| Session ownership and command lifecycle | `frontend/{session,execution,lease,handle,observation,operations}` | `tests/frontend`, `tests/contracts` |
| Bounded output and subscriptions | `frontend/{capture,output,finalization}` | `tests/frontend` |
| Native process and byte transports | `backends/native/{process,channels,containment,termination}` | `tests/backends/native` |
| Native command protocol | `backends/native/{driver,preparation,syntax,bridge}` | `tests/backends/native` |
| Bash syntax and sudo | `backends/bash/{syntax,containment,authentication,password_channel}` | `tests/backends/bash` |
| PowerShell and cmd syntax | `backends/powershell/{syntax,driver.ps1}`; `backends/cmd/syntax` | native and common contract tests |
| Windows process containment | `backends/windows/{containment,limits}` | `tests/backends/native/test_platform_containment.py` |
| Deterministic application double | `backends/mock/{session,driver,scenario}` | `tests/backends/mock`, `tests/contracts` |

Quality tools live in `scripts/quality`; packaging and release operations live in
`scripts/release`. Shared test fixtures belong in `tests/support`. Keep shell
language details in their backend instead of branching throughout the frontend.

Value models do not start processes or perform I/O. The common frontend owns
submission, queuing, cancellation, and final results. Drivers own transport
resources. Both drivers implement the same protocol and feed the same bounded
capture and input interfaces. Mock code cannot call native driver methods.

Each session owns one idle interpreter, one execution lease, and all its submitted
commands. Command-specific pipes isolate business input and output from shell
control messages. A bridge invokes structural processes with argv while inheriting
the shell's current directory and exported environment. Native scripts run in the
existing interpreter scope. Wrapper state uses the reserved `sn_`/`$sn_` namespace;
Bash reserves file descriptor 9 for status messages. Scripts that corrupt the
protocol invalidate the session rather than causing transparent restart.

Windows uses IOCP named pipes and a Job Object assigned before user commands.
POSIX uses private FIFOs and a new process group. Native shells are trusted:
programs that deliberately escape a process group are outside that containment
guarantee. Active Windows elevation is rejected.

The shared submission frontend resolves `SessionConfig.sudo_password` into a
captured asynchronous provider only for an elevated request without its own
provider. Both native and mock drivers use their existing authentication paths.
The configured secret stays out of child environment and configuration serialization.

Capture retains bounded tails and rolling match windows. Each file destination
has a dedicated single-worker executor; transport backpressure limits outstanding
writes. Subscriber queues are bounded and cannot backpressure primary capture.
File bytes are called durable only after flush and fsync complete.

Tests must mock external connectivity. Filesystem tests own a TemporaryDirectory.
Contract tests assert behavior through the public factory; unit tests exercise
failure boundaries with narrowly scoped fakes. Integration tests assert native
semantics and process cleanup instead of merely checking an echo command.

Production modules are limited to 200 code-bearing physical lines. Production
classes and functions use descriptive names without underscore prefixes, except
Python protocol dunders. Every function and value class uses English rST
documentation with parameter, return, and intentional-exception documentation.
Ruff, strict mypy, structural policy checks, and 100% combined branch coverage are
release gates. Platform-specific tests contribute coverage across the OS matrix;
coverage must not be lowered or platform implementations excluded to pass release.
