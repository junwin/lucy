from __future__ import annotations

from typing import Any, Dict, List

from src.storage.base import Storage
from src.utils.text_snippet_loader import load_text_snippet


def get_document_context(
    storage: Storage,
    account_name: str,
    query: str,
    *,
    kind: str | None = None,
    limit: int = 3,
    max_chars: int = 2000,
) -> List[Dict[str, Any]]:
    """Retrieve simple context snippets from documents for a query.

    This is a thin helper over the storage layer that:

    1. Uses the storage backend's "poor man's" document search to find
       relevant documents.
    2. Loads a bounded text snippet from each document's path.

    It does *not* perform any model-based summarisation; callers can decide
    how to present these snippets in prompts or further process them.

    Args:
        storage: Storage implementation (e.g. JsonFileStorage).
        account_name: Account to search documents for.
        query: Free-text query string.
        kind: Optional document kind filter (e.g. "obsidian_note").
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
