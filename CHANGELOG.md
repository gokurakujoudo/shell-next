# Changelog

## Unreleased

- Retain the original submitted command in finalized results, including failures
  and commands stopped before execution.
- Add `CommandResult.stdout_str()` and `stderr_str()` to decode retained tails
  with configurable encoding and error handling (UTF-8 with replacement by default).
- Document and verify configurable stdout/stderr tail bounds through
  `CaptureConfig.tail_bytes`, including the existing 64 KiB per-stream default.

## 0.1.1

- Add CI, required coverage, PyPI, Python-version, and license badges to the README.
- Include branded, searchable documentation and review-ready wiki drafts.
- Deploy GitHub Pages from `main` and keep logo/edit links valid after branch cleanup.
- Add documentation build tooling and generated-site validation.
- Make release uploads independent of Windows progress-display encoding.

The package runtime API is unchanged from 0.1.0.

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
