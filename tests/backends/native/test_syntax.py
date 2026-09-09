import pytest

from shell_next.backends.cmd.syntax import quote
from shell_next.errors import ConfigurationError


@pytest.mark.parametrize("character", ['"', "%", "!", "\n", "\r"])
def test_cmd_control_paths_reject_expansion_and_injection(character: str) -> None:
    with pytest.raises(ConfigurationError):
        quote("path" + character)
