"""Structural subprocess execution inside the current shell's exported state."""

import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

from shell_next.backends.bash.authentication import authenticate


def main(path: str) -> int:
    """Run a JSON-described executable without interpreting its arguments as shell text.

    :param path: Private command manifest containing argv and pipe endpoints.
    :returns: Native process exit code, or 127 if the executable cannot start.
    """
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    with (
        open(manifest["stdout"], "wb", buffering=0) as stdout,
        open(manifest["stderr"], "wb", buffering=0) as stderr,
        open(manifest["stdin"], "rb", buffering=0) as stdin,
    ):
        argv = manifest["argv"]
        try:
            if manifest.get("elevated"):
                with ExitStack() as stack:
                    requests = responses = None
                    if manifest["interactive"]:
                        requests = stack.enter_context(
                            open(manifest["auth_out"], "wb", buffering=0)
                        )
                        responses = stack.enter_context(
                            open(manifest["auth_in"], "rb", buffering=0)
                        )
                        print(manifest["token"] + ":auth_ready", flush=True)
                    authenticated, attempts = authenticate(
                        manifest["target"],
                        manifest["attempts"],
                        (manifest["token"] + "-password:").encode("ascii"),
                        requests,
                        responses,
                    )
                print(f"{manifest['token']}:auth:{int(authenticated)}:{attempts}", flush=True)
                if not authenticated:
                    print(manifest["token"] + ":ready", flush=True)
                    return 126
                argv = [
                    "sudo",
                    "-n",
                    *(["-u", manifest["target"]] if manifest["target"] else []),
                    "--",
                    *argv,
                ]
            print(manifest["token"] + ":ready", flush=True)
            return subprocess.run(argv, stdin=stdin, stdout=stdout, stderr=stderr).returncode
        except OSError:
            print(manifest["token"] + ":ready", flush=True)
            print(manifest["token"] + ":startup_failure", flush=True)
            stderr.write(b"shell-next: executable could not start\n")
            return 127


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
