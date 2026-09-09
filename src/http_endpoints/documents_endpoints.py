"""HTTP document endpoints using CoALA SemanticMemory.

This endpoint implementation serves document search requests by calling
SemanticMemory.recall(SemanticMemoryRequest). It no longer depends on the
old DocumentStore interface or its search_documents_poor_man method.
"""

import logging
from pathlib import Path
from typing import List, Any

from src.coala_memory.semantic import SemanticMemory, SemanticMemoryRequest
from src.prompt_builders.prompt_builder import DEFAULT_SEARCH_NAMESPACES


def _parse_namespaces(raw) -> List[str]:
    if raw is None:
        return list(DEFAULT_SEARCH_NAMESPACES)
    if isinstance(raw, list):
        cleaned = [str(x).strip() for x in raw if str(x).strip()]
        if cleaned:
            return cleaned
        return list(DEFAULT_SEARCH_NAMESPACES)
    s = str(raw or "")
    parts = [p.strip() for p in s.split(",")]
    cleaned = [p for p in parts if p]
    if not cleaned:
        return list(DEFAULT_SEARCH_NAMESPACES)
    return cleaned


def _to_response_item(account_name: str, doc: Any) -> dict:
    return {
        "id": Path(doc.source_id).stem,
        "source_id": doc.source_id,
        "account_name": account_name,
        "path": doc.path or "",
        "source_type": getattr(doc, "source_type", None),
        "title": getattr(doc, "title", ""),
        "tags": list(getattr(doc, "tags", []) or []),
        "snippet": getattr(doc, "snippet", ""),
        "score": getattr(doc, "score", None),
        "truncated": bool(getattr(doc, "truncated", False)),
        "metadata": getattr(doc, "metadata", {}) or {},
    }


def search_documents_impl(semantic_memory: SemanticMemory, data: dict):
    account_name = (data.get("account_name", "") or "").lower()
    query = data.get("question") or data.get("q") or ""
    limit = int(data.get("limit", 10))
    source_type = data.get("source_type")
    namespaces_raw = data.get("namespaces")

    if not account_name:
        return {"error": "Missing account_name"}, 400
    if not query or not str(query).strip():
        return {"error": "Missing query"}, 400

    namespaces = _parse_namespaces(namespaces_raw)

    try:
        req = SemanticMemoryRequest(
            account_name=account_name,
            query=str(query),
            use_embeddings=True,
            namespaces=namespaces,
            top_k=limit,
            max_chars=9000,
            score_threshold=0.25,
            source_type=source_type,
        )

        result = semantic_memory.recall(req)

        if not result or not getattr(result, "documents", None):
            return [], 200

        items = [
            _to_response_item(account_name, d) for d in getattr(result, "documents", [])
        ]

        return items, 200
    except Exception as e:
        logging.exception("Error in /documents/search semantic recall")
        return {"error": str(e)}, 500
