from __future__ import annotations

from typing import Any, Dict, List, Optional

from .task import Task
from .task_list import TaskList
from .tasklist_manager import TaskListManager

__all__ = [
    "Task",
    "TaskList",
    "TaskListManager",
    "get_tasklist",
    "save_tasklist",
    "list_tasklist_ids",
]


def get_tasklist(account_name: str, tasklist_id: str, storage=None) -> Optional[Dict[str, Any]]:
    """Load a persisted tasklist and return a plain dict (TaskListModel).

    Parameters:
    - account_name: storage account namespace
    - tasklist_id: id of the tasklist
    - storage: optional Storage instance implementing get_tasklist

    Returns None when the template does not exist.

    The storage argument is required; when not provided a RuntimeError is raised
    to make dependency requirements explicit.
    """
    if storage is None:
        raise RuntimeError("storage argument is required")
    return storage.get_tasklist(account_name, tasklist_id)


def save_tasklist(account_name: str, tasklist_id: str, tasklist_model: Any, storage=None) -> None:
    """Save a TaskListModel (plain dict) as a template for the account.

    The storage argument is required; when not provided a RuntimeError is
    raised.
    """
    if storage is None:
        raise RuntimeError("storage argument is required")
    return storage.save_tasklist(account_name, tasklist_id, tasklist_model)


def list_tasklist_ids(account_name: str, storage=None) -> List[str]:
    """Return list of template ids for the given account (may be empty).

    The storage argument is required; when not provided a RuntimeError is
    raised.
    """
    if storage is None:
        raise RuntimeError("storage argument is required")
    return storage.list_tasklists(account_name)
