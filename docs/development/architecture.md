# Architecture

The public entry point is `use_shell_session(SessionConfig(...))`. The factory
selects the implementation before entering the session, including the official
`config._session_cls` injection point. Application code should depend on this
interface instead of constructing native adapters.

## Dependency boundaries

| Responsibility | Modules | Tests |
| --- | --- | --- |
| Value validation and immutable contracts | commands, config, capabilities, state, results, input, privilege, errors | tests/unit/test_models.py |
| Session ownership and command lifecycle | session, execution, handle, operations | tests/contracts |
| Bounded output and subscriptions | capture, output | tests/unit/test_capture.py |
| Native process and byte transports | native_process, containment, channels | tests/integration |
| Native command protocol and syntax | native_driver, native_syntax, process_bridge | tests/integration |
| Deterministic application double | mock, mock_driver, mock_scenario | tests/unit/test_mock.py and tests/contracts |

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
