"""Lucy constructor adapter for galet-tools' exact-text edit handler."""
from galet_tools.tools.text_replace_handler import TextReplaceHandler as GaletTextReplaceHandler
from src.handlers.galet_adapters import LucyStorageLocationResolver


class TextReplaceHandler(GaletTextReplaceHandler):
    def __init__(self, config):
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))
