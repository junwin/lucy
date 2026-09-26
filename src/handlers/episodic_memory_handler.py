"""Lucy constructor adapter for galet-tools' episodic_memory handler."""

from galet_tools.tools.episodic_memory_handler import (
    EpisodicMemoryHandler as GaletEpisodicMemoryHandler,
)


class EpisodicMemoryHandler(GaletEpisodicMemoryHandler):
    def __init__(self, config, memory=None):
        self.config = config
        super().__init__(memory=memory)


__all__ = ["EpisodicMemoryHandler"]
