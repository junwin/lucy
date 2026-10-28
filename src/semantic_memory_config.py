"""Compose Galet recall over Lucy's fallback embedding storage."""
from pathlib import Path

from galet_memory import SqliteEpisodicMemory, VectorSemanticMemory

from src.embeddings.memory_adapters import (
    LucyEmbeddingIndex, LucyEmbeddingProvider, LucyTextLoader,
)


def build_semantic_memory(*, embedding_facade, embedding_store, episodic_store):
    return VectorSemanticMemory(
        embeddings=LucyEmbeddingProvider(embedding_facade),
        index=LucyEmbeddingIndex(embedding_store),
        text_loader=LucyTextLoader(),
        episodic_store=episodic_store,
    )


class FileDigestValidator:
    """Borrow the configured episodic DB only while a standalone tool checks a digest.

    Container-backed recall borrows its injected store instead. Standalone tool
    construction opens no database and holds no additional SQLite connection.
    """

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def is_digest_valid(self, **kwargs):
        if not self.db_path.is_file():
            return False
        with SqliteEpisodicMemory(self.db_path, initialize_schema=False) as memory:
            return memory.is_digest_valid(**kwargs)
