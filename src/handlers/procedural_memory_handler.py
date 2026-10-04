"""Lucy composition adapter for galet-tools' procedural_memory handler."""

from galet_tools.tools.procedural_memory_handler import (
    ProceduralMemoryHandler as GaletProceduralMemoryHandler,
)

from src.procedural_memory_config import build_procedural_memory


class ProceduralMemoryHandler(GaletProceduralMemoryHandler):
    def __init__(self, config, memory=None):
        self.config = config
        if memory is None and config is not None:
            memory = build_procedural_memory(config)
        super().__init__(memory=memory)


__all__ = ["ProceduralMemoryHandler"]
