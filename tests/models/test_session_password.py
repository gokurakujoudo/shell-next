import json
from typing import Any, cast

import pytest

from shell_next import SessionConfig
from shell_next.errors import ConfigurationError


@pytest.mark.parametrize("secret", ["supplied-password", b"supplied-password", "", b"", "密码"])
def test_session_password_accepts_text_and_bytes_without_disclosure(secret: str | bytes) -> None:
    config = SessionConfig(sudo_password=secret)
    expected = secret.encode("utf-8") if isinstance(secret, str) else secret
    assert config.sudo_password == expected
    assert config == SessionConfig()
    assert "sudo_password" not in repr(config)
    assert "sudo_password" not in json.dumps(config.to_dict())
    assert config.env == {}


@pytest.mark.parametrize(
    "secret", [123, bytearray(b"secret"), "bad\nsecret", b"bad\rsecret", b"bad\0secret", "\ud800"]
)
def test_invalid_session_password_has_generic_diagnostic(secret: object) -> None:
    with pytest.raises(ConfigurationError, match="Invalid sudo password") as error:
        SessionConfig(sudo_password=cast(Any, secret))
    assert str(error.value) == "Invalid sudo password"
