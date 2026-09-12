# Environment variables

Exported environment variables are inherited by later external commands on
Bash, PowerShell, and cmd. The Python parent remains unchanged.

1. Supply an initial override through `SessionConfig.env` and query it by name.
2. Update it with `set_env()` and read it from an external Python process.
   `get_env()` without a name returns the observed environment dictionary and
   refreshes the cached snapshot. Avoid printing the whole environment because
   it may contain credentials.
3. Remove the variable with `unset_env()`; a subsequent lookup returns `None`.

Portable names are shell identifiers, for example `BUILD_MODE`. Native shell
variables are different: Bash locals and PowerShell variables are not exported;
cmd `set` variables are environment variables. Use the next chapter for native
syntax. Environment queries need enough output retention for their JSON reply;
a very small `tail_bytes` can cause `SessionProtocolError`.

## Full example

File: [`examples/03-environment.py`](https://github.com/gokurakujoudo/shell-next/blob/main/examples/03-environment.py).

```console
python examples/03-environment.py bash
```

On Windows replace `bash` with `powershell` or `cmd`.

<!-- python-doc-exec native: 03-environment.py -->
```python
"""Configure, update, inspect, and remove an exported session variable."""

import asyncio
import os
import sys

from shell_next import Backend, ProcessCommand, SessionConfig, use_shell_session


async def main(backend: Backend) -> None:
    parent_value = os.environ.get("SHELL_NEXT_DEMO_MODE")
    config = SessionConfig(
        backend=backend, env={"SHELL_NEXT_DEMO_MODE": "preview"}, startup_timeout=30
    )
    async with use_shell_session(config) as shell:
        # 1. Initial overrides belong to this session, not the Python parent.
        assert await shell.get_env("SHELL_NEXT_DEMO_MODE") == "preview"
        assert os.environ.get("SHELL_NEXT_DEMO_MODE") == parent_value

        # 2. A later process inherits updates made through the portable helper.
        await shell.set_env("SHELL_NEXT_DEMO_MODE", "release candidate")
        command = ProcessCommand(
            sys.executable, ("-c", "import os; print(os.environ['SHELL_NEXT_DEMO_MODE'])")
        )
        result = await shell.run(command, check=True)
        assert result.stdout_str().strip() == "release candidate"
        environment = await shell.get_env()
        assert isinstance(environment, dict)
        assert environment["SHELL_NEXT_DEMO_MODE"] == "release candidate"
        assert dict(shell.snapshot().environment)["SHELL_NEXT_DEMO_MODE"] == "release candidate"

        # 3. Remove the variable explicitly; None means it is absent.
        await shell.unset_env("SHELL_NEXT_DEMO_MODE")
        assert await shell.get_env("SHELL_NEXT_DEMO_MODE") is None
        assert os.environ.get("SHELL_NEXT_DEMO_MODE") == parent_value
        print("Session environment updated and removed")


if __name__ == "__main__":
    selected = sys.argv[1] if len(sys.argv) > 1 else ("cmd" if os.name == "nt" else "bash")
    asyncio.run(main(Backend(selected)))
```

[Tutorial contents](index.md)
