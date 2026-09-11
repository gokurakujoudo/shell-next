"""Immutable command descriptions; native scripts are deliberately not translated."""

from dataclasses import dataclass

from shell_next.errors import ConfigurationError
from shell_next.models.representation import RecordRepr


@dataclass(frozen=True, repr=False)
class ProcessCommand(RecordRepr):
    """An executable and structural arguments, never interpolated as shell syntax.

    :param executable: Executable name or path; must be nonempty and NUL-free.
    :param args: Ordered NUL-free arguments, copied to an immutable tuple.
    """

    executable: str
    args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate process arguments before any operating-system action.

        :raises ConfigurationError: An executable or argument contains NUL.
        """
        object.__setattr__(self, "args", tuple(self.args))
        if not self.executable or any("\0" in x for x in (self.executable, *self.args)):
            raise ConfigurationError("Executable and arguments must be NUL-free")


@dataclass(frozen=True, repr=False)
class SessionScript(RecordRepr):
    """Native script text executed in the persistent shell's scope.

    :param text: Backend-native text; NUL is not accepted.
    """

    text: str

    def __post_init__(self) -> None:
        """Reject text that native shell command transports cannot represent.

        :raises ConfigurationError: The script contains NUL.
        """
        if "\0" in self.text:
            raise ConfigurationError("Script must be NUL-free")


type Command = ProcessCommand | SessionScript
"""Public command union; structural processes and native scripts have distinct semantics."""
