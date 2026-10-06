"""Composition helper for the application-level curation service.

Concrete storage/provider selection remains owned by ``container_config``.
This module merely asks the configured container for the neutral interfaces
needed by ``CurationEngine`` so handlers do not construct backends themselves.
"""

from __future__ import annotations

from src.episodic import LucyEpisodicStore

from functools import lru_cache
from pathlib import Path

from galet.interface import LLMApi

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
    episodic_store = container.get(LucyEpisodicStore)
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
        embedding_facade=embedding_facade,
        storage=embedding_store,
    )


@lru_cache(maxsize=1)
def get_curation_service():
    """Compose the shared append-only archive/reset service."""
    from galet_memory import CurationService
    from galet_memory.publication import EmbeddingDigestPublisher, FilesystemDigestStore
    from src.handlers.curate_chat_handler import LucyDigestGenerator
    from src.curation.digest_publication_adapters import LucyEmbeddingIndex, LucyEmbeddingProvider
    engine = get_curation_engine()
    publisher = None
    if engine.embedding_facade is not None and engine.storage is not None:
        publisher = EmbeddingDigestPublisher(
            FilesystemDigestStore(engine.digests_root),
            LucyEmbeddingProvider(engine.embedding_facade), LucyEmbeddingIndex(engine.storage),
        )
    return CurationService(engine.episodic_store, LucyDigestGenerator(engine), digest_publisher=publisher)
