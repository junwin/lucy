from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.storage.interfaces import DocumentStore
from src.utils.text_snippet_loader import load_text_snippet


def get_document_context(
    storage: DocumentStore,
    account_name: str,
    query: str,
    *,
    kind: str | None = None,
    docs_tag: str | None = None,
    limit: int = 3,
    max_chars: int = 6000,
) -> List[Dict[str, Any]]:
    """Retrieve simple context snippets from documents for a query.

    This is a thin helper over the storage layer that:

    1. Uses the storage backend's "poor man's" document search to find
       relevant documents when no tag is specified.
    2. If docs_tag is provided, it will strictly filter eligible documents
       using the storage.list_documents(tag=...). In that mode the returned
       documents are the (up to `limit`) documents with the given tag and kind
       — relevance to `query` is not additionally enforced.
    3. Loads a bounded text snippet from each document's path.

    It does *not* perform any model-based summarisation; callers can decide
    how to present these snippets in prompts or further process them.

    Args:
        storage: Storage implementation (e.g. JsonFileStorage).
        account_name: Account to search documents for.
        query: Free-text query string. Ignored when docs_tag is set.
        kind: Optional document kind filter (e.g. "obsidian_note").
        docs_tag: Optional tag that strictly filters documents via
                  storage.list_documents(tag=...).
        limit: Maximum number of documents to return.
        max_chars: Maximum characters to load per document.

    Returns:
        A list of dictionaries with keys:
            - id
            - title
            - path
            - tags
            - snippet
            - truncated (bool)
    """

    logging.debug("get_document_context: docs_tag=%s", docs_tag)

    # We currently rely on the JsonFileStorage-specific helper. If a future
    # storage backend does not implement this, callers should handle that
    # before calling this helper.
    if not hasattr(storage, "search_documents_poor_man"):
        return []
    
    results = storage.search_documents_poor_man(
        account_name=account_name,
        query=query,
        kind=kind,
        limit=limit,
        tag=docs_tag,
    )



    contexts: List[Dict[str, Any]] = []

    for doc in results:
        snippet, truncated = load_text_snippet(doc.path, max_chars=max_chars)

        contexts.append(
            {
                "id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "tags": list(doc.tags),
                "snippet": snippet,
                "truncated": truncated,
            }
        )

    return contexts


def get_document_context_traced(
    storage: DocumentStore,
    account_name: str,
    query: str,
    *,
    kind: str | None = None,
    docs_tag: str | None = None,
    limit: int = 3,
    max_chars: int = 6000,
    keywords: Any | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Retrieve document context snippets *and* return a full scoring trace.

    Works identically to :func:`get_document_context` but additionally
    returns a second value: a ``trace`` dictionary that captures every
    decision the enrichment pipeline made so it can be inspected later
    without re-running the search.

    The trace dictionary has the shape::

        {
            "query": str,
            "query_keywords": [str, ...],
            "candidates": [
                {
                    "id": str,
                    "title": str | None,
                    "tags": [str, ...],
                    "doc_keywords": [str, ...],
                    "matched_terms": [str, ...],
                    "score": int,
                    "selected": bool,
                },
                ...
            ],
            "selected": [
                {
                    "id": str,
                    "title": str | None,
                    "path": str,
                    "tags": [str, ...],
                    "score": int,
                    "matched_terms": [str, ...],
                    "truncated": bool,
                    "snippet_len": int,
                },
                ...
            ],
            "params": {
                "kind": str | None,
                "docs_tag": str | None,
                "limit": int,
                "max_chars": int,
            },
        }

    Args:
        storage: Storage implementation.
        account_name: Account to search documents for.
        query: Free-text query string.
        kind: Optional document kind filter.
        docs_tag: Optional tag filter.
        limit: Maximum number of documents to return.
        max_chars: Maximum characters to load per document.
        keywords: Optional pre-instantiated Keywords utility. When provided,
                  avoids the overhead of loading spaCy on every call. Useful
                  for bulk evaluation.

    Returns:
        A ``(contexts, trace)`` tuple.
    """
    from src.keywords.keywords import Keywords

    if keywords is None:
        keywords = Keywords()

    query_keywords = keywords.extract_keywords(query, top_n=20)

    trace: Dict[str, Any] = {
        "query": query,
        "query_keywords": query_keywords,
        "candidates": [],
        "selected": [],
        "params": {
            "kind": kind,
            "docs_tag": docs_tag,
            "limit": limit,
            "max_chars": max_chars,
        },
    }

    # ------------------------------------------------------------------
    # Replicate the search_documents_poor_man scoring loop so we can
    # capture every candidate's score, matched terms, etc.
    # ------------------------------------------------------------------
    if not hasattr(storage, "list_documents"):
        return [], trace

    candidate_docs = storage.list_documents(
        account_name=account_name,
        kind=kind,
        tag=docs_tag,
        select_limit=100,
    )

    scored: List[Tuple[Any, int, List[str]]] = []  # (doc, score, matched_terms)

    for doc in candidate_docs:
        title_text = (doc.title or "").lower()
        tags_text = " ".join(doc.tags).lower()
        metadata_text = " ".join(
            str(v).lower() for v in (doc.metadata or {}).values()
        )
        blob = " ".join([title_text, tags_text, metadata_text])
        doc_keywords = keywords.extract_keywords(blob, top_n=50)

        matched_terms = sorted(set(doc_keywords) & set(query_keywords))
        score = len(matched_terms)

        trace["candidates"].append(
            {
                "id": doc.id,
                "title": doc.title,
                "tags": list(doc.tags),
                "doc_keywords": doc_keywords,
                "matched_terms": matched_terms,
                "score": score,
                "selected": False,  # filled in below
            }
        )

        if score > 0:
            scored.append((doc, score, matched_terms))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_docs = scored[:limit]

    # Mark which candidates were selected
    selected_ids = {doc.id for doc, _, _ in top_docs}
    for c in trace["candidates"]:
        if c["id"] in selected_ids:
            c["selected"] = True

    # ------------------------------------------------------------------
    # Load snippets for the selected docs (same as get_document_context)
    # ------------------------------------------------------------------
    contexts: List[Dict[str, Any]] = []

    for doc, score, matched_terms in top_docs:
        snippet, truncated = load_text_snippet(doc.path, max_chars=max_chars)

        contexts.append(
            {
                "id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "tags": list(doc.tags),
                "snippet": snippet,
                "truncated": truncated,
            }
        )

        trace["selected"].append(
            {
                "id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "tags": list(doc.tags),
                "score": score,
                "matched_terms": matched_terms,
                "truncated": truncated,
                "snippet_len": len(snippet),
            }
        )

    return contexts, trace
