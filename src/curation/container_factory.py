"""Composition helper for the application-level curation service.

Concrete storage/provider selection remains owned by ``container_config``.
This module merely asks the configured container for the neutral interfaces
needed by ``CurationEngine`` so handlers do not construct backends themselves.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from galet.interface import LLMApi

from src.coala_memory.episodic import EpisodicMemoryManager
from src.config_manager import ConfigManager
from src.curation.core import CurationEngine
from src.embeddings.facade import EmbeddingFacade
from src.storage.interfaces import EmbeddingStore


@lru_cache(maxsize=1)
def get_curation_engine() -> CurationEngine:
    """Return the process-wide curation service using configured interfaces."""
    # Deliberately imported at call time to avoid a container/handler import cycle.
    from src.container_config import container

    if container is None:
        raise RuntimeError("dependency injection container is not configured")

    config = container.get(ConfigManager)
    episodic_store = container.get(EpisodicMemoryManager)
    llm_api = container.get(LLMApi)
    embedding_facade = container.get(EmbeddingFacade)
    embedding_store = container.get(EmbeddingStore)

    external_roots = config.get("external_roots", {}) or {}
    lucy_data_root = external_roots.get(
        "lucy_data_files", "/home/junwin/lucy_storage"
    )
    data_base = Path(lucy_data_root) / "data"

    return CurationEngine(
        episodic_store=episodic_store,
        llm_api=llm_api,
        llm_model=config.get("curation_llm_model", "gpt-4o-mini"),
        digests_root=data_base / "digests",
        archives_root=data_base / "archives",
        embedding_facade=embedding_facade,
        storage=embedding_store,
    )
