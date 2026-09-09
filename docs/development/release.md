# First release gates

No stable tag or PyPI publication is permitted until these gates are verified.
The version remains an alpha while implementation and validation are incomplete.

- Common behavioral contracts pass for Mock, Bash, PowerShell 7, and cmd.
- Bash reference testing includes RHEL 8, persistent state, large simultaneous
  streams, descendant cleanup, cancellation races, and ignored soft termination.
- Interactive sudo, cached credentials, wrong passwords, authentication deadlines,
  separate business stdin, and strict privileged-cleanup rejection pass.
- PowerShell and cmd pass native script, structural process, persistent state,
  timeout, cancellation, containment, and unsupported-elevation tests.
- Mock tests prohibit real subprocesses, filesystem writes, network access,
  environment/directory mutation, and real sleeps.
- Ruff, strict mypy, production policy checks, and **100% branch coverage** pass.
- Repeated lifecycle stress tests detect no process, handle, task, or thread leaks.
- Wheel and sdist build, metadata checks, and installed-wheel smoke tests pass.
- GitHub release artifacts are built from the tested commit.
- PyPI publication uses a configured trusted publisher or the maintainer's existing
  local PyPI credential configuration.

The optional GitHub publishing workflow uses an environment named `pypi` and
the PyPA trusted publisher action. Local publication uses Twine after the same
exact-commit verification. Credentials are never committed to the repository or
printed by release tooling. A draft release does not establish that gates passed.
