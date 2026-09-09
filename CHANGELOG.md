# Changelog

## 0.1.0

- Persistent Bash, PowerShell 7, and cmd sessions for Python 3.14+.
- Structural process arguments and native scripts with persistent shell state.
- Managed commands, scoped handles, FIFO queuing, independent observation deadlines,
  and bounded interruption and cleanup.
- Manual and planned stdin, literal prompt matching, bounded byte capture,
  optional durable files, and independent output subscribers.
- Interactive/noninteractive Bash sudo with separate authentication channels.
- Strict deterministic mock scenarios through `SessionConfig._session_cls`.
- RHEL 8, Linux, and Windows contracts, installed-wheel checks, static analysis,
  and 100% combined branch coverage as publication gates.

Active Windows elevation, terminal emulation, and strict cleanup of privileged
descendants are unsupported. Forced interruption invalidates the persistent
session; callers create a new session explicitly.
