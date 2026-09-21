from __future__ import annotations

from galet_tools.tools.video_generate_handler import (
    VideoGenerateHandler as GaletVideoGenerateHandler,
)

from src.config_manager import ConfigManager
from src.handlers.galet_adapters import LucyStorageLocationResolver


class VideoGenerateHandler(GaletVideoGenerateHandler):
    """Lucy adapter for Galet-tools video generation."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))
