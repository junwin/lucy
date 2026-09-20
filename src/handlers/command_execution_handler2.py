"""Lucy compatibility adapter for galet-tools' structured command handler."""

from galet_tools.host.security import DefaultSecurityPolicy
from galet_tools.tools.execute_command2 import ExecuteCommand2 as GaletExecuteCommand2

from src.handlers.galet_adapters import (
    LucySandboxRootResolver,
    LucyStorageLocationResolver,
)


class CommandExecutionHandler2(GaletExecuteCommand2):
    """Construct Galet's structured command handler from Lucy's ConfigManager."""

    # Preserve Lucy's existing public tool name so agent permissions, skills,
    # and lazy-tool selection do not need to migrate at the same time.
    NAME = "execute_command"

    def __init__(self, config) -> None:
        self.config = config
        self._lucy_security_policy = DefaultSecurityPolicy()
        super().__init__(
            LucyStorageLocationResolver(config),
            LucySandboxRootResolver(config),
            self._lucy_security_policy,
        )


__all__ = ["CommandExecutionHandler2"]
