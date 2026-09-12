"""Lucy compatibility adapter for galet-tools' file_load handler."""

from galet_tools.tools.file_load_handler2 import (
    FileLoadHandler2 as GaletFileLoadHandler2,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class FileLoadHandler2(GaletFileLoadHandler2):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["FileLoadHandler2"]
