# Step-by-step tutorial

Learn the implemented shell-next features through small operations, then combine
them into a working report job. Each chapter has one to three examples, ordered
from simple to more involved, and a complete standalone Python file in
[`examples/`](https://github.com/gokurakujoudo/shell-next/tree/main/examples).
Assertions explain observable results; no external account or project is needed
except when you explicitly choose the sudo chapter.

## Setup and backend selection

Install Python 3.14+ and shell-next 0.1.3 or newer, then use a repository checkout to access the
example files (they are not installed as package entry points):

```console
python -m pip install shell-next
```

Run from the checkout root. Pick the backend supported by your host:

| Host | Shell prerequisite | Example command |
| --- | --- | --- |
| Linux, including the RHEL 8 reference platform | Bash | `python examples/01-commands.py bash` |
| Windows | PowerShell 7 (`pwsh`) | `python examples/01-commands.py powershell` |
| Windows | cmd (provided by Windows) | `python examples/01-commands.py cmd` |

Repeat the selected backend argument for each native chapter. Without it,
examples default to cmd on Windows and Bash on Linux. The mock chapter needs no
backend argument. Sudo requires an explicit backend and mode. In a checkout under
development use `python -m pip install -e ".[dev,docs]"` in your environment first.

Every file has imports, an async entry point, assertions, and an `asyncio.run()`
guard. In an existing async application await `main(...)` instead of nesting
`asyncio.run()`. `startup_timeout=30` gives cold PowerShell startup a larger budget.
To select a non-default shell location, supply `SessionConfig.executable`.

## Chapters

1. [Ordinary and multiple commands](01-commands.md)
2. [Directory navigation](02-navigation.md)
3. [Environment variables](03-environment.md)
4. [Native scripts and script files](04-scripts.md)
5. [Output decoding and full capture](05-capture.md)
6. [Interactive input and live events](06-input-and-events.md)
7. [Failures, observation deadlines, and stopping](07-errors-and-lifecycle.md)
8. [Queued and concurrent work](08-concurrency.md)
9. [Sudo and backend capabilities](09-sudo.md)
10. [Deterministic application tests](10-mocking.md)
11. [A complete workspace workflow](11-workflow.md)
