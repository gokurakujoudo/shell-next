"""First-class session test double using the production ownership frontend."""

import posixpath
from dataclasses import replace

from shell_next.backends.mock.driver import MockDriver
from shell_next.backends.mock.scenario import MockScenario
from shell_next.errors import ConfigurationError
from shell_next.frontend.session import ShellSession
from shell_next.models.config import SessionConfig
from shell_next.models.state import Backend


class MockShellSession(ShellSession):
    """Side-effect-free session with virtual state and strict command expectations.

    :param config: Normal application session configuration.
    :param scenario: Optional predetermined commands and interactions.
    """

    def __init__(self, config: SessionConfig, scenario: MockScenario | None = None) -> None:
        """Replace native transport before session entry and disable implicit files.

        :param config: Normal session configuration.
        :param scenario: Strict scenario, or a new empty strict scenario.
        """
        super().__init__(replace(config, capture=replace(config.capture, directory=None)))
        self.scenario = scenario if scenario is not None else MockScenario()
        self.driver = MockDriver(self.scenario, self)
        self.cwd = config.cwd or ("C:\\" if config.backend != Backend.BASH else "/")
        self.session_id = "mock-session"
        self.command_count = 0

    def next_command_id(self) -> str:
        """Allocate deterministic scenario-local identifiers.

        :returns: Sequential readable mock command identifier.
        """
        self.command_count += 1
        return f"mock-command-{self.command_count}"

    @classmethod
    def configured(cls, scenario: MockScenario) -> type[MockShellSession]:
        """Bind a scenario to the official config._session_cls injection point.

        :param scenario: Predetermined application behavior to assert.
        :returns: Session implementation class bound to this scenario.
        """

        class ScenarioSession(MockShellSession):
            """Session implementation bound to one explicitly supplied test scenario."""

            def __init__(self, config: SessionConfig) -> None:
                """Attach the bound scenario without affecting application configuration.

                :param config: Application's normal configuration.
                """
                super().__init__(config, scenario)

        return ScenarioSession

    def clock(self) -> float:
        """Read virtual time without consulting the real monotonic clock.

        :returns: Scenario time in simulated seconds.
        """
        return self.scenario.elapsed

    def record(self, operation: str, *args: object) -> None:
        """Record ordered observable operations with pre-redacted secret payloads.

        :param operation: Operation name.
        :param args: Safe arguments; input secrets have already been redacted.
        """
        self.scenario.calls.append((operation, *args))

    async def __aexit__(self, *exc: object) -> None:
        """Close and validate strict expectations without masking a body exception.

        :param exc: Python context exception information.
        :raises MockExpectationNotConsumedError: Required expectations remain unused.
        """
        await self.aclose()
        if not exc or exc[0] is None:
            self.scenario.assert_consumed()

    async def chdir(self, path: str) -> None:
        """Change only virtual working-directory state.

        :param path: Virtual path; POSIX relative paths resolve against virtual cwd.
        """
        self.cwd = posixpath.normpath(posixpath.join(self.cwd or "/", path))
        self.record("chdir", path)

    async def set_env(self, name: str, value: str) -> None:
        """Update only the virtual exported environment.

        :param name: Nonempty environment name without equals or NUL.
        :param value: NUL-free environment value.
        :raises ConfigurationError: The name or value is invalid.
        """
        if not name or "=" in name or "\0" in name + value:
            raise ConfigurationError("Invalid environment name or value")
        self.environment[name] = value
        self.record("set_env", name)

    async def unset_env(self, name: str) -> None:
        """Remove an exported variable from the virtual environment.

        :param name: Virtual variable name.
        """
        self.environment.pop(name, None)
        self.record("unset_env", name)

    async def get_cwd(self) -> str:
        """Read the virtual working directory without calling os.getcwd.

        :returns: Virtual directory string.
        """
        self.record("get_cwd")
        return self.cwd or "/"

    async def get_env(self, name: str | None = None) -> str | dict[str, str] | None:
        """Read virtual exported state without consulting os.environ.

        :param name: Specific variable or None for a copied environment view.
        :returns: Value, missing marker, or copied environment dictionary.
        """
        self.record("get_env", name)
        return self.environment.get(name) if name is not None else dict(self.environment)

    async def ping(self) -> bool:
        """Observe virtual session health without consuming a user expectation.

        :returns: Whether the mock remains usable.
        """
        self.record("ping")
        return self.is_usable
