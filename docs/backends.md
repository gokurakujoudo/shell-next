# Backend support

| Capability | Bash on Linux | PowerShell 7 on Windows | cmd on Windows |
| --- | --- | --- | --- |
| Persistent cwd and environment | Yes | Yes | Yes |
| Native local variables | Yes | Yes | Yes |
| Native functions and aliases | Yes | Yes | No |
| Structural process argv | Yes | Yes | Yes |
| Separate stdout and stderr | Yes | Yes | Yes |
| Ordered business stdin | Yes | Yes | Yes |
| Literal stream prompt matching | Yes | Yes | Yes |
| Cooperative stop attempt | Yes | No | No |
| Forceful containment cleanup | Process group | Windows Job Object | Windows Job Object |
| Active sudo elevation | Yes | No | No |
| Terminal or Host prompt automation | No | No | No |
| Guaranteed reuse after interruption | No | No | No |

Read `shell.capabilities` for the immutable capability record. Unsupported
privilege requests fail before command submission.

## Bash

RHEL 8 is the reference platform. Normal native scripts run in the persistent
shell scope. Bash descriptor 9 and the `sn_` namespace are reserved for the
control protocol.

Interactive sudo authentication uses private channels and a unique prompt.
`SessionConfig.sudo_password` supplies an upfront text/bytes secret for elevated
commands without an explicit provider; ordinary commands retain their identity.
Passwords are separate from business stdin and capture. Cached credentials do
not cause unnecessary provider calls. Elevated scripts run in a separate
elevated Bash process, so their state does not persist in the ordinary session.
Strict cleanup of privileged descendants is unsupported and rejected.

## PowerShell

PowerShell 7 must be installed and discoverable as `pwsh`, or selected using
`SessionConfig.executable`. Native process output preserves bytes. Script
results report last-success, native exit code, and terminating-error status
separately; inspect `result.status` rather than assuming every failure is one
numeric exit code.

Host-level prompts and terminal interfaces are unsupported. Active Windows
elevation is rejected. Ordinary descendant cleanup uses a Job Object assigned
before user commands execute.

## cmd

cmd provides the compatibility backend with persistent variables and cwd.
Structural process arguments remain literal. Control paths and portable state
helper values that cmd cannot quote safely are rejected explicitly. Use
`ProcessCommand` when arguments contain shell metacharacters.

## Containment boundary

The library manages trusted native shells. POSIX programs that deliberately
escape a process group are outside the containment guarantee. Results record
cleanup uncertainty, and forced interruption makes the session unusable.

See [results and capture](usage.md#results-and-capture) and
[troubleshooting](troubleshooting.md) for interpreting failures.
