"""Lucy compatibility adapter for galet-tools' repo_index handler."""

from galet_tools.tools.repo_index_handler import (
    RepoIndexHandler as GaletRepoIndexHandler,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class RepoIndexHandler(GaletRepoIndexHandler):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["RepoIndexHandler"]
