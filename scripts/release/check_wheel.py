"""Build and verify package installation in a temporary, isolated virtual environment."""

import os
import subprocess
import sys
import venv
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, "-m", "build"], cwd=root, check=True)
    wheels = list((root / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Exactly one current wheel is required for installation validation")
    with TemporaryDirectory(prefix="shell-next-wheel-") as temporary:
        directory = Path(temporary)
        venv.EnvBuilder(with_pip=True).create(directory / "venv")
        interpreter = (
            directory / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        subprocess.run(
            [str(interpreter), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [str(interpreter), "-I", str(root / "scripts/release/wheel_probe.py")],
            cwd=directory,
            check=True,
        )


if __name__ == "__main__":
    main()
