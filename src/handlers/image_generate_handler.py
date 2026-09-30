"""Lucy configuration adapter for Galet-tools AI image generation."""
from galet_tools.tools.image_generate_handler import ImageGenerateHandler as GaletImageGenerateHandler
from src.handlers.galet_adapters import LucyStorageLocationResolver

class ImageGenerateHandler(GaletImageGenerateHandler):
    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))
