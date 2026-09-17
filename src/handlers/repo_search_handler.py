"""Lucy compatibility adapter for galet-tools' repo_search handler."""

from galet_tools.tools.repo_search_handler import (
    RepoSearchHandler as GaletRepoSearchHandler,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class RepoSearchHandler(GaletRepoSearchHandler):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))


__all__ = ["RepoSearchHandler"]
