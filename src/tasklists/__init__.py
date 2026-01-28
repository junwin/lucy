"""Package-level helpers for tasklist persistence boundary.

This module re-exports the simple boundary functions used by higher-level
application code. The boundary works with plain Python structures (TaskListModel
~ dict) and delegates to tasklist_boundary which converts to/from the domain
TaskList and persists via TaskListStorage.

Functions:
- get_tasklist(account_name, tasklist_id) -> dict | None
- save_tasklist(account_name, tasklist_id, tasklist_model) -> None
- list_tasklist_ids(account_name) -> list[str]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


__all__ = ["get_tasklist", "save_tasklist", "list_tasklist_ids"]


def get_tasklist(account_name: str, tasklist_id: str) -> Optional[Dict[str, Any]]:
    """Load a persisted tasklist template and return a TaskListModel (plain dict).

    Returns None when the template does not exist.
    """
    return _get_tasklist(account_name, tasklist_id)


def save_tasklist(account_name: str, tasklist_id: str, tasklist_model: Any) -> None:
    """Save a TaskListModel (plain dict) as a template for the account.

    The boundary will create directories as needed. tasklist_model may be a
    dict-like object or a JSON string.
    """
    return _save_tasklist(account_name, tasklist_id, tasklist_model)


def list_tasklist_ids(account_name: str) -> List[str]:
    """Return list of template ids for the given account (may be empty)."""
    return _list_tasklist_ids(account_name)
