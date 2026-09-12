"""Lucy compatibility adapter for galet-tools' file_save handler."""

from galet_tools.tools.file_save_handler import (
    FileSaveHandler2 as GaletFileSaveHandler2,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class FileSaveHandler2(GaletFileSaveHandler2):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["FileSaveHandler2"]
