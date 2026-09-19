"""Lucy compatibility adapter for galet-tools' execute_command handler."""

from galet_tools.host.security import DefaultSecurityPolicy
from galet_tools.tools.command_execution_handler2 import (
    CommandExecutionHandler2 as GaletCommandExecutionHandler2,
)

from src.handlers.galet_adapters import (
    LucySandboxRootResolver,
    LucyStorageLocationResolver,
)


class CommandExecutionHandler2(GaletCommandExecutionHandler2):
    """Construct Galet's command handler from Lucy's ConfigManager."""

    def __init__(self, config) -> None:
        self.config = config
        self._lucy_security_policy = DefaultSecurityPolicy()
        super().__init__(
            LucyStorageLocationResolver(config),
            LucySandboxRootResolver(config),
            self._lucy_security_policy,
        )

    def execute(self, args, *, account_name: str = "auto"):
        result = super().execute(args, account_name=account_name)
        if result.get("error") == "Command refused by security policy":
            result["error"] = (
                "Command refused by security policy: interactive commands are "
                "not allowed. If shell syntax is required, use an explicit "
                "non-interactive wrapper such as bash -lc 'pwd'. Do not "
                "repeat the rejected command unchanged."
            )
        return result


__all__ = ["CommandExecutionHandler2"]
