"""Frontend authentication transport, isolated from business input and capture."""

from typing import TYPE_CHECKING

from shell_next.errors import PrivilegeAuthenticationError

if TYPE_CHECKING:
    from shell_next.backends.native.channels import CommandChannel
    from shell_next.frontend.handle import CommandHandle


async def supply_passwords(
    handle: CommandHandle, requests: CommandChannel, responses: CommandChannel
) -> None:
    """Call a secret supplier only for explicit private sudo password requests.

    :param handle: Command holding the configured asynchronous password provider.
    :param requests: Private authentication request channel.
    :param responses: Private secret response channel.
    :raises PrivilegeAuthenticationError: The request or supplied secret is invalid.
    """
    request = handle.options.privilege
    provider = request.password_provider
    assert provider is not None
    count = 0
    buffer = bytearray()
    while data := await requests.read(64):
        buffer.extend(data)
        if len(buffer) > 128:
            raise PrivilegeAuthenticationError("Invalid authentication request")
        while b"\n" in buffer:
            line, _, remaining = buffer.partition(b"\n")
            buffer[:] = remaining
            if line != b"password" or count >= request.attempts:
                raise PrivilegeAuthenticationError("Authentication attempt limit reached")
            password = await provider()
            if not isinstance(password, bytes) or any(
                value in password for value in (b"\n", b"\r", b"\0")
            ):
                raise PrivilegeAuthenticationError("Password provider returned an invalid secret")
            await responses.send(password + b"\n")
            del password
            count += 1
