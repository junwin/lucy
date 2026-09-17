"""Lucy compatibility adapter for galet-tools' patch_apply handler."""

from galet_tools.tools.patch_apply_handler import (
    PatchApplyHandler2 as GaletPatchApplyHandler2,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class PatchApplyHandler(GaletPatchApplyHandler2):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["PatchApplyHandler"]
