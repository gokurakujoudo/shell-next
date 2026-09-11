"""Explicit immutable feature discovery for native backends."""

from dataclasses import dataclass

from shell_next.models.representation import RecordRepr
from shell_next.models.state import Backend


@dataclass(frozen=True, repr=False)
class SessionCapabilities(RecordRepr):
    """Boolean capabilities with conservative interruption and terminal guarantees.

    :param persistent_state: Shell state survives normal commands.
    :param working_directory: Portable directory operations are available.
    :param environment: Portable environment operations are available.
    :param local_variables: Native variables survive normal scripts.
    :param functions: Native functions survive normal scripts.
    :param aliases: Native aliases are supported.
    :param session_script: Native scripts can be executed.
    :param process_command: Structural executable invocation is supported.
    :param separate_streams: Standard output and error remain separate.
    :param logical_streams: Backend-specific logical stream labels are available.
    :param raw_process_bytes: Structural process output preserves bytes.
    :param sequential_input: Ordered standard input is available.
    :param prompt_matching: Literal stream prompts can be matched.
    :param native_stdin: Structural processes accept interactive standard input.
    :param host_prompts: Host-level prompt automation is guaranteed.
    :param terminal: A terminal transport is available.
    :param soft_stop: A non-forceful termination request is available.
    :param force_stop: Forceful cleanup is available.
    :param process_containment: Descendants belong to an OS containment unit.
    :param survives_interruption: Session reuse after arbitrary interruption is guaranteed.
    :param privilege_execution: Active privilege elevation is supported.
    :param interactive_privilege: Separate password authentication is supported.
    :param strict_privileged_cleanup: All privileged descendants can be forcefully cleaned up.
    """

    persistent_state: bool = True
    working_directory: bool = True
    environment: bool = True
    local_variables: bool = True
    functions: bool = True
    aliases: bool = True
    session_script: bool = True
    process_command: bool = True
    separate_streams: bool = True
    logical_streams: bool = False
    raw_process_bytes: bool = True
    sequential_input: bool = True
    prompt_matching: bool = True
    native_stdin: bool = True
    host_prompts: bool = False
    terminal: bool = False
    soft_stop: bool = False
    force_stop: bool = True
    process_containment: bool = True
    survives_interruption: bool = False
    privilege_execution: bool = False
    interactive_privilege: bool = False
    strict_privileged_cleanup: bool = False


def backend_capabilities(backend: Backend) -> SessionCapabilities:
    """Construct first-release capability defaults for a native language.

    :param backend: Selected shell language.
    :returns: Immutable conservative capability record.
    """
    return SessionCapabilities(
        functions=backend != Backend.CMD,
        aliases=backend != Backend.CMD,
        soft_stop=backend == Backend.BASH,
        privilege_execution=backend == Backend.BASH,
        interactive_privilege=backend == Backend.BASH,
    )
