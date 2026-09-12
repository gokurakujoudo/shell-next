import asyncio

import pytest

from shell_next import (
    Backend,
    CommandOptions,
    ConcurrencyPolicy,
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    PrivilegeRequest,
    ProcessCommand,
    SessionConfig,
    use_shell_session,
)
from shell_next.errors import PrivilegeAuthenticationError, PrivilegeUnsupportedError


@pytest.mark.parametrize("use_defaults", [False, True])
async def test_session_password_reused_only_when_authentication_is_requested(
    use_defaults: bool,
) -> None:
    command = ProcessCommand("identity")
    scenario = MockScenario(
        [
            MockExpectation(command, (Emit(b"root"),), authentication_prompts=prompts)
            for prompts in (1, 0, 1)
        ]
    )
    options = CommandOptions(privilege=PrivilegeRequest(requirement="elevated"))
    config = SessionConfig(
        sudo_password="upfront-secret", _session_cls=MockShellSession.configured(scenario)
    )
    if use_defaults:
        config.defaults = options
    async with use_shell_session(config) as shell:
        for prompts in (1, 0, 1):
            handle = shell.submit(command, options=None if use_defaults else options, check=True)
            assert handle.options.privilege.interactive
            provider = handle.options.privilege.password_provider
            assert provider is not None and await provider() == b"upfront-secret"
            result = await handle.wait()
            assert result.privilege.authenticated and result.privilege.attempts == prompts
            assert result.stdout_str() == "root"
            assert "upfront-secret" not in repr((result, handle, shell, shell.snapshot(), config))
        assert await shell.get_env("sudo_password") is None
    assert not options.privilege.interactive and options.privilege.password_provider is None
    assert sum(call[0] == "authenticate" for call in scenario.calls) == 2
    assert "upfront-secret" not in repr(scenario.calls)


async def test_explicit_provider_overrides_session_secret_without_fallback() -> None:
    calls = 0

    async def provider() -> bytes:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider-secret")

    command = ProcessCommand("identity")
    scenario = MockScenario([MockExpectation(command, authentication_prompts=1)])
    config = SessionConfig(
        sudo_password=b"session-secret", _session_cls=MockShellSession.configured(scenario)
    )
    options = CommandOptions(
        privilege=PrivilegeRequest(
            requirement="elevated",
            interactive=True,
            password_provider=provider,
        )
    )
    async with use_shell_session(config) as shell:
        with pytest.raises(PrivilegeAuthenticationError) as error:
            await shell.run(command, options=options, check=True)
        assert calls == 1
        assert "secret" not in repr(error.value.result)
    assert "secret" not in repr(scenario.calls)


async def test_queued_submissions_capture_their_own_password_values() -> None:
    command = ProcessCommand("identity")
    scenario = MockScenario([MockExpectation(command, authentication_prompts=1) for _ in range(2)])
    config = SessionConfig(
        sudo_password=b"first-secret",
        concurrency=ConcurrencyPolicy.QUEUE,
        defaults=CommandOptions(privilege=PrivilegeRequest(requirement="elevated")),
        _session_cls=MockShellSession.configured(scenario),
    )
    async with use_shell_session(config) as shell:
        first = shell.submit(command)
        shell.config.sudo_password = "second-secret"
        second = shell.submit(command)
        for handle, expected in ((first, b"first-secret"), (second, b"second-secret")):
            provider = handle.options.privilege.password_provider
            assert provider is not None and await provider() == expected
        assert all(result.success for result in await asyncio.gather(first.wait(), second.wait()))
    assert "secret" not in repr(scenario.calls)


@pytest.mark.parametrize("backend", list(Backend))
async def test_session_password_does_not_elevate_ordinary_commands(backend: Backend) -> None:
    command = ProcessCommand("ordinary")
    scenario = MockScenario([MockExpectation(command)])
    config = SessionConfig(
        backend=backend, sudo_password=b"secret", _session_cls=MockShellSession.configured(scenario)
    )
    async with use_shell_session(config) as shell:
        result = await shell.run(command, check=True)
        assert not result.privilege.requested
        if backend != Backend.BASH:
            with pytest.raises(PrivilegeUnsupportedError):
                shell.submit(
                    command,
                    options=CommandOptions(privilege=PrivilegeRequest(requirement="elevated")),
                )
    assert not any(call[0] == "authenticate" for call in scenario.calls)


async def test_rejected_upfront_password_reports_failure_and_attempt_limit() -> None:
    command = ProcessCommand("identity")
    scenario = MockScenario(
        [MockExpectation(command, authentication_prompts=3, authenticated=False)]
    )
    config = SessionConfig(
        sudo_password=b"wrong-secret", _session_cls=MockShellSession.configured(scenario)
    )
    options = CommandOptions(privilege=PrivilegeRequest(requirement="elevated", attempts=2))
    async with use_shell_session(config) as shell:
        with pytest.raises(PrivilegeAuthenticationError) as error:
            await shell.run(command, options=options, check=True)
        result = error.value.result
        assert result is not None and not result.success
        assert result.privilege.attempts == 2
        assert "wrong-secret" not in repr(result)
