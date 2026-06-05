"""Debug endpoint for analysing prompt builder document loading effectiveness.

Provides a /prompt_builder/debug route that returns the full pipeline trace:
  - Keywords extracted from the query
  - All scored documents (with scores and matched terms)
  - Which docs were selected
  - Snippet lengths and truncation status

This is a read-only diagnostic tool — it does not modify any state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.agent import AgentManager
from src.config_manager import ConfigManager
from src.storage.base import Storage
from src.utils.document_context import get_document_context
from src.utils.text_snippet_loader import load_text_snippet
from src.keywords.keywords import Keywords


def prompt_builder_debug_impl(
    storage: Storage,
    config: ConfigManager,
    payload: dict,
) -> Tuple[Any, int]:
    """Analyse what documents would be loaded for a given query.

    Returns a detailed trace of the document loading pipeline without
    actually building a prompt or modifying any state.
    """
    query = payload.get("query", "")
    account_name = (payload.get("accountName") or "").lower()
    context_name = payload.get("contextName") or payload.get("context_name")
    docs_tag: Optional[str] = None

    if not query or not account_name:
        return {"error": "Missing query or accountName"}, 400

    # --- Stage 1: Extract keywords ---
    kw_util = Keywords()
    keywords = kw_util.extract_keywords(query, top_n=20)

    # --- Stage 2: Get docs_tag from context if available ---
    if context_name and context_name != "none":
        try:
            if hasattr(storage, "get_or_create_context"):
                ctx = storage.get_or_create_context(account_name, context_name)
            else:
                ctx = storage.get_context(account_name, context_name)
            if ctx is not None:
                data = getattr(ctx, "data", None)
                if isinstance(data, dict):
                    tag_val = data.get("tag")
                    if isinstance(tag_val, str) and tag_val.strip():
                        docs_tag = tag_val.strip()
        except Exception as ex:
            logging.warning("prompt_builder_debug: failed to load context %s: %s", context_name, ex)

    # --- Stage 3: Search documents (poor man's) ---
    raw_scored: List[Dict[str, Any]] = []
    if hasattr(storage, "search_documents_poor_man"):
        # Get all candidates first (no limit) to see full scoring picture
        candidates = storage.list_documents(
            account_name=account_name,
            kind="obsidian_note",
            tag=docs_tag,
            select_limit=100,
        )

        terms = keywords  # already extracted above

        for doc in candidates:
            title_text = (doc.title or "").lower()
            tags_text = " ".join(doc.tags).lower()
            metadata_text = " ".join(
                str(v).lower() for v in (doc.metadata or {}).values()
            )

            blob = " ".join([title_text, tags_text, metadata_text])
            blob_keywords = kw_util.extract_keywords(blob, top_n=50)

            matched = list(set(blob_keywords) & set(terms))
            score = len(matched)

            raw_scored.append({
                "id": doc.id,
                "title": doc.title,
                "tags": list(doc.tags),
                "path": doc.path,
                "score": score,
                "matched_terms": matched,
            })

        # Sort by score descending
        raw_scored.sort(key=lambda x: x["score"], reverse=True)

    # --- Stage 4: What get_document_context would select (top 3, max 9000 chars) ---
    selected_docs = get_document_context(
        storage=storage,
        account_name=account_name,
        query=query,
        kind="obsidian_note",
        docs_tag=docs_tag,
        limit=3,
        max_chars=9000,
    )

    selected_info: List[Dict[str, Any]] = []
    for doc in selected_docs:
        # Re-load snippet to report length info
        snippet, truncated = load_text_snippet(doc["path"], max_chars=9000)
        selected_info.append({
            "id": doc["id"],
            "title": doc["title"],
            "path": doc["path"],
            "tags": doc["tags"],
            "snippet_length": len(snippet),
            "truncated": truncated,
            "snippet_preview": snippet[:200] + ("..." if len(snippet) > 200 else ""),
        })

    # --- Build result ---
    result = {
        "query": query,
        "keywords_extracted": keywords,
        "docs_tag_from_context": docs_tag,
        "all_scored_docs": raw_scored[:20],  # top 20 for readability
        "docs_selected_by_get_document_context": selected_info,
        "summary": {
            "total_candidates": len(raw_scored),
            "docs_with_positive_score": sum(1 for d in raw_scored if d["score"] > 0),
            "docs_selected": len(selected_info),
        },
    }

    return result, 200
