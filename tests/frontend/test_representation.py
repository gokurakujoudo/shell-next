from shell_next import (
    Emit,
    MockExpectation,
    MockScenario,
    MockShellSession,
    ProcessCommand,
    SessionConfig,
    ShellSession,
)


async def test_session_and_handle_representations_follow_lifecycle_without_observation() -> None:
    native = ShellSession(SessionConfig())
    assert "state=SessionState.NEW" in repr(native)
    assert "pending=0" in repr(native)
    command = ProcessCommand("payload-hidden-from-handle")
    scenario = MockScenario([MockExpectation(command, (Emit(b"hello"), Emit(b"oops", "stderr")))])
    session = MockShellSession(SessionConfig(env={"TOKEN": "private-env"}), scenario)
    assert repr(session).startswith("MockShellSession(")
    async with session:
        handle = session.submit(command)
        calls = list(scenario.calls)
        assert "state=SessionState.OPEN" in repr(session) and "pending=1" in repr(session)
        assert "state='queued'" in repr(handle) and "done=False" in repr(handle)
        assert "payload-hidden-from-handle" not in repr(handle)
        assert "private-env" not in repr(session)
        assert scenario.calls == calls
        await handle.wait()
        assert "state='finished'" in repr(handle) and "done=True" in repr(handle)
        assert "stdout_bytes=5" in repr(handle) and "stderr_bytes=4" in repr(handle)
        assert "pending=0" in repr(session)
    assert "state=SessionState.CLOSED" in repr(session)
