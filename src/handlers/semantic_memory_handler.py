"""Lucy composition adapter for galet-tools' semantic_memory handler."""

from galet.embedding_router import EmbeddingRouter
from galet.mistral_embedding import MistralEmbeddingApi
from galet.openai_embedding import OpenAIEmbeddingApi
from galet.settings import Settings
from galet_tools.tools.semantic_memory_handler import (
    SemanticMemoryHandler as GaletSemanticMemoryHandler,
)

from src.coala_memory.semantic import SqliteVecSemanticMemory
from src.embeddings.facade import EmbeddingFacade
from src.storage.primitives_embedding_store import build_primitives_embedding_store


class SemanticMemoryHandler(GaletSemanticMemoryHandler):
    def __init__(self, config, memory=None):
        self.config = config
        if memory is None:
            settings = Settings(
                credential_path=config.get("credential_path"),
                ollama_base_url=config.get("ollama_base_url"),
            )
            facade = EmbeddingFacade(
                embedding_api=EmbeddingRouter(
                    openai_api=OpenAIEmbeddingApi(settings=settings),
                    mistral_api=MistralEmbeddingApi(settings=settings),
                )
            )
            memory = SqliteVecSemanticMemory(
                embedding_facade=facade,
                embedding_store=build_primitives_embedding_store(config),
            )
        else:
            facade = getattr(memory, "embedding_facade", None)
        super().__init__(memory, embedding_facade=facade)


__all__ = ["SemanticMemoryHandler"]
