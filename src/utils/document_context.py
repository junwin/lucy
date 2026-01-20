from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.storage.base import Storage
from src.utils.text_snippet_loader import load_text_snippet


def get_document_context(
    storage: Storage,
    account_name: str,
    query: str,
    *,
    kind: str | None = None,
    docs_tag: str | None = None,
    limit: int = 3,
    max_chars: int = 2000,
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

    if docs_tag is not None:
        # Strict tag-based listing: use list_documents to filter the eligible
        # documents. This guarantees we only consider documents that expose
        # the requested tag. We respect `kind` and `limit` here.
        if not hasattr(storage, "list_documents"):
            return []

        results = storage.list_documents(
            account_name=account_name,
            kind=kind,
            tag=docs_tag,
            limit=limit,
        )
    else:
        # Backwards-compatible behaviour: use the poor-man search which
        # scores documents based on the free-text query.
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
