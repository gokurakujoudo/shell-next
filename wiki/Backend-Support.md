# Backend support

| Backend | Platform | Main distinction |
| --- | --- | --- |
| Bash | Linux; RHEL 8 reference | Native shell state and separate-channel sudo authentication. |
| PowerShell 7 | Windows | Native PowerShell state and separate success/error dimensions. |
| cmd | Windows | Compatibility execution with persistent cwd and variables. |

All three support structural process arguments, separate stdout/stderr, ordered
business stdin, literal prompt matching, and bounded capture. Read
`shell.capabilities` before requesting backend-specific features.

Terminal emulation, PowerShell Host prompts, and active Windows elevation are
unsupported. Windows containment uses Job Objects; Linux uses process groups.
Deliberate process-group escape and strict privileged-descendant cleanup are
outside the guarantee. Requests for strict privileged cleanup are rejected.

Elevated Bash scripts run in a separate elevated interpreter, so their state
does not persist in the ordinary session. Passwords are supplied through private
authentication channels, never business stdin.

See the [complete backend guide](https://gokurakujoudo.github.io/shell-next/backends/).
