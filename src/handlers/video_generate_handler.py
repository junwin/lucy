"""Lucy compatibility adapter for galet-tools' video_generate handler."""

from galet_tools.tools.video_generate_handler import (
    VideoGenerateHandler as GaletVideoGenerateHandler,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class VideoGenerateHandler(GaletVideoGenerateHandler):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["VideoGenerateHandler"]
