"""Backend-native wrapper construction; only private paths enter control text."""

from pathlib import Path

from shell_next.backends.bash import syntax as bash
from shell_next.backends.cmd import syntax as cmd
from shell_next.backends.powershell import syntax as powershell
from shell_next.models.state import Backend


def quote(value: str, backend: Backend) -> str:
    """Dispatch literal quoting to the selected native language.

    :param value: Literal word.
    :param backend: Selected language.
    :returns: Native quoted word.
    """
    quote_value = {
        Backend.BASH: bash.quote,
        Backend.CMD: cmd.quote,
        Backend.POWERSHELL: powershell.quote,
    }[backend]
    return quote_value(value)


def invocation(argv: list[str], backend: Backend) -> str:
    """Represent trusted bridge paths as a native executable invocation.

    :param argv: Executable and private manifest arguments, never business argv.
    :param backend: Selected native language.
    :returns: Native invocation text.
    """
    prefix = (
        "& " if backend == Backend.POWERSHELL else "command " if backend == Backend.BASH else ""
    )
    return prefix + " ".join(quote(arg, backend) for arg in argv)


def command_wrapper(
    backend: Backend, invocation_text: str, token: str, script: bool, channels: dict[str, str]
) -> str:
    """Build command-local redirection and private status reporting.

    :param backend: Native language.
    :param invocation_text: Trusted invocation of a private script or bridge.
    :param token: Random command control marker.
    :param script: Whether native script stream redirection is needed.
    :param channels: Command-specific stdin, stdout, and stderr endpoints.
    :returns: Wrapper script, preserving native session scope.
    """
    render = {
        Backend.BASH: bash.wrapper,
        Backend.CMD: cmd.wrapper,
        Backend.POWERSHELL: powershell.wrapper,
    }[backend]
    return render(invocation_text, token, script, channels)


def source_script(path: Path, backend: Backend) -> str:
    """Invoke a private script in the persistent native scope.

    :param path: Script file containing user-native text.
    :param backend: Selected language.
    :returns: Dot-source or call expression.
    """
    return ("call " if backend == Backend.CMD else ". ") + quote(str(path), backend)
