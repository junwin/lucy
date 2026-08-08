"""embeddings handler — generate and compare vector embeddings.

Supports four operations:
- **embed** — generate embeddings for one or more texts
- **compare** — score two vectors with a distance metric
- **rank** — rank a query vector against many candidates
- **search** — embed a query text, then search stored embeddings via Storage
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.embeddings import DistanceMetric, EmbeddingFacade
from src.embeddings.registry import known_models
from src.handlers.handler_v2 import HandlerV2
from src.llm.embedding_dto import EmbeddingResponse

logger = logging.getLogger(__name__)


class EmbeddingHandler(HandlerV2):
    """Handler for embedding generation and vector comparison."""

    NAME = "embeddings"

    def __init__(self, config: ConfigManager):
        self.config = config
        self.facade = EmbeddingFacade()

    # ------------------------------------------------------------------
    # HandlerV2 interface
    # ------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Generate embeddings, compare vectors, or search stored embeddings. "
                "Use 'embed' to convert text to vectors. Use 'compare' for two vectors. "
                "Use 'rank' to score a query vector against many candidates. "
                "Use 'search' to embed a query text and find the closest stored embeddings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["embed", "compare", "rank", "search", "models"],
                        "description": (
                            "Operation: 'embed' generates vectors for texts, "
                            "'compare' scores two vectors, "
                            "'rank' scores a query vector against candidates, "
                            "'search' embeds a query and searches stored embeddings, "
                            "'models' lists known embedding models."
                        ),
                    },
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Texts to embed (for 'embed' and 'search' actions).",
                        "default": [],
                    },
                    "model": {
                        "type": "string",
                        "description": "Embedding model name, e.g. 'text-embedding-3-small' or 'mistral-embed'.",
                        "default": "text-embedding-3-small",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["cosine", "euclidean", "dot_product"],
                        "description": "Distance metric for 'compare', 'rank', 'search'.",
                        "default": "cosine",
                    },
                    "vector_a": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "First vector (for 'compare').",
                        "default": [],
                    },
                    "vector_b": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Second vector (for 'compare').",
                        "default": [],
                    },
                    "query_vector": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Query vector for 'rank' action.",
                        "default": [],
                    },
                    "candidates": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "Candidate vectors for 'rank' action.",
                        "default": [],
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top results to return (for 'rank', 'search').",
                        "default": 5,
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Embedding namespace for 'search' (e.g. 'documents').",
                        "default": "",
                    },
                    "account_name": {
                        "type": "string",
                        "description": "Account name for 'search' (e.g. 'junwin').",
                        "default": "",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Optional source_type filter for 'search'.",
                        "default": "",
                    },
                },
                "required": [
                    "action",
                    "texts",
                    "model",
                    "metric",
                    "vector_a",
                    "vector_b",
                    "query_vector",
                    "candidates",
                    "top_k",
                    "namespace",
                    "account_name",
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
                "action": {"type": "string"},
                "error": {"type": "string"},
                "model": {"type": "string"},
                "embeddings": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                "score": {"type": "number"},
                "metric": {"type": "string"},
                "ranked": {"type": "array"},
                "results": {"type": "array"},
                "models": {"type": "object"},
            },
            "required": ["ok", "action"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        action = str(args.get("action", "")).strip()

        if action == "embed":
            return self._do_embed(args)
        elif action == "compare":
            return self._do_compare(args)
        elif action == "rank":
            return self._do_rank(args)
        elif action == "search":
            return self._do_search(args)
        elif action == "models":
            return self._do_models()
        else:
            return {
                "ok": False,
                "action": action,
                "error": f"Unknown action: {action!r}. Use embed, compare, rank, search, or models.",
            }

    # ------------------------------------------------------------------
    # action: embed
    # ------------------------------------------------------------------

    def _do_embed(self, args: Dict[str, Any]) -> Dict[str, Any]:
        texts: List[str] = args.get("texts", [])
        model: str = str(args.get("model", "text-embedding-3-small")).strip()

        if not texts:
            return {
                "ok": False,
                "action": "embed",
                "error": "No texts provided. Pass a 'texts' list.",
            }
        if not model:
            return {
                "ok": False,
                "action": "embed",
                "error": "No model specified.",
            }

        logger.info("embeddings: embed %d texts with model=%s", len(texts), model)

        try:
            resp: EmbeddingResponse = self.facade.embed(texts, model=model)
        except Exception as exc:
            logger.exception("embeddings: embed failed")
            return {
                "ok": False,
                "action": "embed",
                "error": f"Embedding failed: {type(exc).__name__}: {exc}",
            }

        return {
            "ok": True,
            "action": "embed",
            "model": resp.model,
            "embeddings": resp.embeddings,
            "count": len(resp.embeddings),
        }

    # ------------------------------------------------------------------
    # action: compare
    # ------------------------------------------------------------------

    def _do_compare(self, args: Dict[str, Any]) -> Dict[str, Any]:
        a: List[float] = args.get("vector_a", [])
        b: List[float] = args.get("vector_b", [])
        metric_name: str = str(args.get("metric", "cosine")).strip()

        if not a or not b:
            return {
                "ok": False,
                "action": "compare",
                "error": "Both 'vector_a' and 'vector_b' are required.",
            }

        metric = self._parse_metric(metric_name)
        if metric is None:
            return {
                "ok": False,
                "action": "compare",
                "error": f"Unknown metric: {metric_name!r}. Use cosine, euclidean, or dot_product.",
            }

        logger.info("embeddings: compare dims=%d vs %d metric=%s", len(a), len(b), metric.value)

        # Determine the actual score function based on metric
        if metric is DistanceMetric.COSINE:
            score = self.facade.cosine_similarity(a, b)
        else:
            from src.embeddings.comparison import _score
            score = _score(a, b, metric)

        return {
            "ok": True,
            "action": "compare",
            "metric": metric.value,
            "score": score,
            "dim_a": len(a),
            "dim_b": len(b),
        }

    # ------------------------------------------------------------------
    # action: rank
    # ------------------------------------------------------------------

    def _do_rank(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query: List[float] = args.get("query_vector", [])
        candidates: List[List[float]] = args.get("candidates", [])
        metric_name: str = str(args.get("metric", "cosine")).strip()
        k: int = int(args.get("top_k", 5))

        if not query:
            return {
                "ok": False,
                "action": "rank",
                "error": "'query_vector' is required.",
            }
        if not candidates:
            return {
                "ok": False,
                "action": "rank",
                "error": "'candidates' list is required.",
            }

        metric = self._parse_metric(metric_name)
        if metric is None:
            return {
                "ok": False,
                "action": "rank",
                "error": f"Unknown metric: {metric_name!r}. Use cosine, euclidean, or dot_product.",
            }

        logger.info(
            "embeddings: rank dim=%d vs %d candidates, metric=%s, k=%d",
            len(query),
            len(candidates),
            metric.value,
            k,
        )

        try:
            results = self.facade.top_k(query, candidates, k=k, metric=metric)
        except Exception as exc:
            logger.exception("embeddings: rank failed")
            return {
                "ok": False,
                "action": "rank",
                "error": f"Rank failed: {type(exc).__name__}: {exc}",
            }

        return {
            "ok": True,
            "action": "rank",
            "metric": metric.value,
            "top_k": k,
            "num_candidates": len(candidates),
            "ranked": [{"index": idx, "score": score} for idx, score in results],
        }

    # ------------------------------------------------------------------
    # action: search
    # ------------------------------------------------------------------

    def _do_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        texts: List[str] = args.get("texts", [])
        model: str = str(args.get("model", "text-embedding-3-small")).strip()
        metric_name: str = str(args.get("metric", "cosine")).strip()
        k: int = int(args.get("top_k", 5))
        namespace: str = str(args.get("namespace", "")).strip()
        account: str = str(args.get("account_name", "")).strip()

        if not texts:
            return {
                "ok": False,
                "action": "search",
                "error": "No query texts provided. Pass 'texts' with one string to embed.",
            }
        if not namespace:
            return {
                "ok": False,
                "action": "search",
                "error": "'namespace' is required for search.",
            }
        if not account:
            return {
                "ok": False,
                "action": "search",
                "error": "'account_name' is required for search.",
            }

        query_text = texts[0]
        logger.info(
            "embeddings: search query=%r namespace=%s account=%s model=%s k=%d",
            query_text[:80],
            namespace,
            account,
            model,
            k,
        )

        # 1. Embed the query
        try:
            resp: EmbeddingResponse = self.facade.embed([query_text], model=model)
        except Exception as exc:
            logger.exception("embeddings: search embed failed")
            return {
                "ok": False,
                "action": "search",
                "error": f"Embedding failed: {type(exc).__name__}: {exc}",
            }

        query_vector = resp.embeddings[0]

        # 2. Query stored embeddings via storage
        source_type: str = str(args.get("source_type", "")).strip()
        filter_dict: Optional[Dict[str, Any]] = None
        if source_type:
            filter_dict = {"source_type": source_type}

        try:
            storage = self._get_storage()
            results = storage.query_embeddings(
                namespaces=[namespace],
                account_name=account,
                query_vector=query_vector,
                top_k=k,
                filter=filter_dict,
            )
        except Exception as exc:
            logger.exception("embeddings: search storage query failed")
            return {
                "ok": False,
                "action": "search",
                "error": f"Storage query failed: {type(exc).__name__}: {exc}",
            }

        return {
            "ok": True,
            "action": "search",
            "model": model,
            "namespace": namespace,
            "account_name": account,
            "query": query_text[:200],
            "results": [
                {
                    "id": rec.id,
                    "source_type": rec.source_type,
                    "source_id": rec.source_id,
                    "score": round(score, 6),
                }
                for rec, score in results
            ],
        }

    # ------------------------------------------------------------------
    # action: models
    # ------------------------------------------------------------------

    def _do_models(self) -> Dict[str, Any]:
        models = {}
        for name, info in known_models().items():
            models[name] = {
                "provider": info.provider,
                "dimensions": info.dimensions,
                "description": info.description,
            }

        return {
            "ok": True,
            "action": "models",
            "models": models,
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_metric(name: str) -> Optional[DistanceMetric]:
        name = name.strip().lower()
        mapping = {
            "cosine": DistanceMetric.COSINE,
            "euclidean": DistanceMetric.EUCLIDEAN,
            "dot_product": DistanceMetric.DOT_PRODUCT,
        }
        return mapping.get(name)

    def _get_storage(self):
        """Lazily construct storage from config."""
        from src.storage.json_file_storage import JsonFileStorage
        from src.storage_paths.storage_paths import StoragePaths

        storage_root = self.config.get("storage_root_path") or "/home/junwin/lucydata"
        storage_ns = self.config.get("storage_namespace") or "data"
        sp = StoragePaths(storage_root, storage_ns)
        return JsonFileStorage(sp)
