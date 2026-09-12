"""Lucy compatibility adapter for galet-tools' generate_image handler."""

from galet_tools.tools.generate_image_handler import (
    GenerateImageHandler as GaletGenerateImageHandler,
)

from src.handlers.galet_adapters import LucyConfigProvider


class GenerateImageHandler(GaletGenerateImageHandler):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyConfigProvider(config))


__all__ = ["GenerateImageHandler"]
