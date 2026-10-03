import logging
from typing import Any, Tuple


def list_context_names_impl(storage, account_name: str, *, procedural_memory=None) -> Tuple[Any, int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400

    try:
        if procedural_memory is not None:
            return procedural_memory.repository.list_resolved_context_names(account_name), 200
        return storage.list_context_names(account_name), 200
    except Exception:
        logging.exception(
            "list_context_names_impl: failed to list context names for account=%s", account_name
        )
        return {"error": "An error occurred"}, 500
