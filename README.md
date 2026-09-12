<p align="center">
  <img src="https://raw.githubusercontent.com/gokurakujoudo/shell-next/main/shell-next-logo.png" alt="shell-next logo" width="300">
</p>

# shell-next

[![CI](https://github.com/gokurakujoudo/shell-next/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/gokurakujoudo/shell-next/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage: 100% required](https://img.shields.io/badge/coverage-100%25%20required-brightgreen)](https://github.com/gokurakujoudo/shell-next/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpypi.org%2Fpypi%2Fshell-next%2Fjson&query=%24.info.version&label=pypi&prefix=v&color=blue&cacheSeconds=300)](https://pypi.org/project/shell-next/)
[![Python](https://img.shields.io/pypi/pyversions/shell-next)](https://pypi.org/project/shell-next/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/gokurakujoudo/shell-next/blob/main/LICENSE)

Persistent asynchronous Bash, PowerShell, and cmd sessions for Python 3.14+.

Bash sudo supports an upfront `SessionConfig(sudo_password=...)` reused by
explicitly elevated commands, or an asynchronous per-command password provider.

Follow the [step-by-step tutorial](docs/tutorials/index.md) for examples from basic
commands through a complete workflow on all three backends. Full standalone code
is in [examples/](examples/README.md).

[Documentation](https://gokurakujoudo.github.io/shell-next/) ·
[PyPI](https://pypi.org/project/shell-next/) · [Wiki drafts](wiki/README.md)

```python
from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def inspect_repository(config: SessionConfig):
    async with use_shell_session(config) as shell:
        await shell.chdir("/srv/project")
        result = await shell.run(ProcessCommand("git", ("status", "--short")), check=True)
        return result.stdout_str()
```

Use `ProcessCommand` for executable arguments that must remain structural. Use
`SessionScript` for backend-native scripts and persistent shell variables,
functions, and aliases. Shell syntax is never translated between languages.

Install with `python -m pip install shell-next`. Supply
`SessionConfig(backend=Backend.BASH)` on Linux, or select `Backend.POWERSHELL`
(PowerShell 7 installed) or `Backend.CMD` on Windows. Python 3.14+ is required.

## Interactive commands

```python
from shell_next import CommandOptions, StdinMode


async def answer_prompt(shell, program):
    options = CommandOptions(stdin=StdinMode.MANUAL)
    async with shell.command(program, options=options, timeout=30) as command:
        await command.expect(b"Name: ")
        await command.sendline(b"Ada")
        await command.close_stdin()
        return await command.wait()
```

`submit()` immediately registers a command and returns its handle. One session
executes one command at a time; the default policy rejects concurrent submissions.
`ConcurrencyPolicy.QUEUE` enables FIFO queuing. Different sessions run independently.

Cancelling `wait()` cancels observation only. Cancelling `run()` or escaping a
command context requests termination. A force-stopped shell becomes unusable;
create another session explicitly when required.

## Deterministic application tests

```python
from shell_next import Emit, MockExpectation, MockScenario, MockShellSession

scenario = MockScenario(
    [
        MockExpectation(ProcessCommand("git", ("status", "--short")), (Emit(b" M README.md\n"),)),
    ]
)
config = SessionConfig()
config._session_cls = MockShellSession.configured(scenario)
```

Pass this same configuration to application code using `use_shell_session`.
The mock shares production lifecycle code while keeping execution, state, input,
and output in memory. Unmatched commands and unconsumed strict expectations fail.
`Advance(60)` advances mock time without sleeping. Plain
`config._session_cls = MockShellSession` creates an empty strict scenario.

## Capture and capabilities

Results retain the original `ProcessCommand` or `SessionScript` as `result.command`.
Use `result.stdout_str()` and `result.stderr_str()` for decoded tail text (UTF-8
with replacement by default), or access raw bytes through `result.stdout.tail`
and `result.stderr.tail`.

Public records have named-field reprs with readable enum names and abbreviated
large payloads. Sessions and command handles show current lifecycle state and
counts. Representations preserve hidden secret fields and do not query the shell.

Set `SessionConfig(capture=CaptureConfig(tail_bytes=4096))` to retain at most
4 KiB per stream; the default is 65,536 bytes (64 KiB), and zero retains no tail.
Each stream retains its own bounded tail, and
literal prompt matching uses a separate bounded window. Slow event subscribers
receive an overflow error without blocking primary capture. Opt into full capture
with `CaptureConfig(directory=existing_directory)`. Results distinguish received
bytes, durable file bytes, truncation, sealing, and possible unread output.

Inspect `shell.capabilities` before requesting backend-specific behavior.
Windows active elevation and terminal/PowerShell Host prompt automation are
unsupported. The library is a process-management API, **not a security sandbox**
for untrusted scripts.

See the [development specification](docs/development/specification.md),
[usage guide](docs/usage.md),
[architecture](docs/development/architecture.md), and
[release checklist](docs/development/release.md).

## Development

```console
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy
python -m pytest --cov --cov-branch
python -m build
python -m twine check dist/*
```

The package uses only the Python standard library at runtime. Tests that start
real shells are marked `integration`. Test files mirror production responsibilities;
reusable test infrastructure lives in `tests/support`.
