import pytest

from shell_next import (
    CommandOptions,
    MockExpectation,
    MockScenario,
    MockShellSession,
    PrivilegeRequest,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)
from shell_next.errors import PrivilegeAuthenticationError


@pytest.mark.parametrize("prompts,authenticated", [(0, True), (1, True), (1, False)])
async def test_mock_privilege_simulation_never_records_passwords(
    prompts: int, authenticated: bool
) -> None:
    calls = 0

    async def password() -> bytes:
        nonlocal calls
        calls += 1
        return b"private-password"

    command = ProcessCommand("virtual")
    scenario = MockScenario(
        [MockExpectation(command, authentication_prompts=prompts, authenticated=authenticated)]
    )
    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated", interactive=True, password_provider=password
        )
    )
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        handle = shell.submit(command, options=options, check=True)
        if authenticated:
            result = await handle.wait()
            assert result.privilege.authenticated
        else:
            with pytest.raises(PrivilegeAuthenticationError) as failure:
                await handle.wait()
            assert failure.value.result is handle.result
    assert calls == prompts
    assert "private-password" not in repr(scenario.calls)


async def test_mock_noninteractive_authentication_failure() -> None:
    command = ProcessCommand("virtual")
    scenario = MockScenario(
        [MockExpectation(command, authentication_prompts=1, authenticated=False)]
    )
    options = CommandOptions(privilege=PrivilegeRequest(requirement="elevated"))
    async with use_shell_session(
        SessionConfig(_session_cls=MockShellSession.configured(scenario))
    ) as shell:
        result = await shell.run(command, options=options)
        assert not result.success and not result.privilege.authenticated
