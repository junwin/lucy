"""HandlerV2 tool for integration-testing CoALA semantic memory via Lucy agents."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from galet.embedding_router import EmbeddingRouter
from galet.mistral_embedding import MistralEmbeddingApi
from galet.openai_embedding import OpenAIEmbeddingApi
from galet.settings import Settings

from src.coala_memory.semantic import SemanticMemoryRequest, SqliteVecSemanticMemory
from src.config_manager import ConfigManager
from src.embeddings.facade import EmbeddingFacade
from src.handlers.handler_v2 import HandlerV2
from src.storage.primitives_embedding_store import build_primitives_embedding_store

logger = logging.getLogger(__name__)


class SemanticMemoryHandler(HandlerV2):
    """Recall durable semantic memory through the CoALA semantic interface.

    This handler is intentionally small and exists primarily as an integration
    seam: Lucy agents can invoke it and inspect the documents returned by
    ``SqliteVecSemanticMemory`` using the same embedding-store configuration as
    the rest of Lucy.
    """

    NAME = "semantic_memory"

    def __init__(self, config: ConfigManager):
        self.config = config
        settings = Settings(
            credential_path=config.get("credential_path"),
            ollama_base_url=config.get("ollama_base_url"),
        )
        embedding_facade = EmbeddingFacade(
            embedding_api=EmbeddingRouter(
                openai_api=OpenAIEmbeddingApi(settings=settings),
                mistral_api=MistralEmbeddingApi(settings=settings),
            )
        )
        embedding_store = build_primitives_embedding_store(config)
        self.memory = SqliteVecSemanticMemory(
            embedding_facade=embedding_facade,
            embedding_store=embedding_store,
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Recall durable semantic memory relevant to a query using Lucy's "
                "configured embedding store. Returns matching documents/snippets "
                "with similarity scores and retrieval metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["recall"],
                        "description": "Operation to perform.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Natural-language query to recall relevant semantic memory.",
                    },
                    "account_name": {
                        "type": "string",
                        "description": "Account whose semantic memory should be searched. Empty uses the caller account.",
                        "default": "",
                    },
                    "namespaces": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Embedding namespaces to search.",
                        "default": ["external"],
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of vector matches to consider.",
                        "default": 3,
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters loaded from each matching source document.",
                        "default": 9000,
                    },
                    "score_threshold": {
                        "type": "number",
                        "description": "Minimum similarity score required for inclusion.",
                        "default": 0.25,
                    },
                    "embedding_model": {
                        "type": "string",
                        "description": "Embedding model used for the query vector.",
                        "default": "text-embedding-3-small",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Optional source_type filter, e.g. 'obsidian_note'.",
                        "default": "",
                    },
                },
                "required": [
                    "action",
                    "query",
                    "account_name",
                    "namespaces",
                    "top_k",
                    "max_chars",
                    "score_threshold",
                    "embedding_model",
                    "source_type",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "query": {"type": "string"},
                "account_name": {"type": "string"},
                "documents": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool", "action"],
            "additionalProperties": True,
        }

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context: Any,
    ) -> Dict[str, Any]:
        action = str(args.get("action") or "").strip().lower()
        if action != "recall":
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": f"Unknown action: {action!r}. Use 'recall'.",
            }

        query = str(args.get("query") or "").strip()
        if not query:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": "query is required",
            }

        requested_account = str(args.get("account_name") or "").strip()
        resolved_account = requested_account or str(account_name or "").strip()
        if not resolved_account or resolved_account == "auto":
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": "account_name is required",
            }

        namespaces_raw = args.get("namespaces") or ["external"]
        namespaces: List[str] = [
            str(value).strip() for value in namespaces_raw if str(value).strip()
        ] or ["external"]

        request = SemanticMemoryRequest(
            account_name=resolved_account,
            query=query,
            use_embeddings=True,
            namespaces=namespaces,
            top_k=max(1, int(args.get("top_k", 3))),
            max_chars=max(1, int(args.get("max_chars", 9000))),
            score_threshold=float(args.get("score_threshold", 0.25)),
            embedding_model=str(
                args.get("embedding_model") or "text-embedding-3-small"
            ).strip(),
            source_type=(str(args.get("source_type") or "").strip() or None),
        )

        try:
            result = self.memory.recall(request)
        except Exception as exc:
            logger.exception("semantic_memory recall failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "query": query,
                "account_name": resolved_account,
                "error": f"{type(exc).__name__}: {exc}",
            }

        documents = [
            {
                "source_id": doc.source_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "snippet": doc.snippet,
                "tags": list(doc.tags),
                "score": doc.score,
                "truncated": doc.truncated,
                "path": doc.path,
                "metadata": dict(doc.metadata),
            }
            for doc in result.documents
        ]

        return {
            "ok": True,
            "tool": self.NAME,
            "action": action,
            "query": query,
            "account_name": resolved_account,
            "documents": documents,
            "count": len(documents),
            "metadata": dict(result.metadata),
        }


__all__ = ["SemanticMemoryHandler"]
