from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.tasklists import TaskList


class TasklistsMixin:
    """Tasklist methods extracted from JsonFileStorage.

    Mixin: relies on self.storage_paths, self._tasklist_service, and
    self._ensure_dir provided by the composing class.
    """

    def _tasklists_dir(self, account_name: str) -> Path:
        # store tasklist templates under documents/<account>/tasklists/
        d = self.storage_paths.tasklists / account_name
        return d

    def _tasklist_path(self, account_name: str, tasklist_id: str) -> Path:
        """Return a resolved, safe Path for a tasklist JSON file using StoragePaths.resolve_relative.

        This ensures user-supplied account names or ids cannot escape the
        storage namespace.
        """
        # Build a relative path under base and resolve via storage_paths
        rel = f"tasklists/{account_name}/{tasklist_id}.json"
        return self.storage_paths.resolve_relative(rel)

    def list_tasklists(self, account_name: str) -> List[str]:
        d = self._tasklists_dir(account_name)
        if not d.exists() or not d.is_dir():
            return []

        ids: List[str] = []
        for p in d.glob("*.json"):
            ids.append(p.stem)

        ids.sort()
        return ids

    def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        """Load a tasklist from storage using TaskListService."""

        path = self._tasklist_path(account_name, tasklist_key)
        try:
            return self._tasklist_service.load(str(path))
        except FileNotFoundError:
            return None

    def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        """Save a tasklist to storage using TaskListService."""

        # Basic id validation: only allow simple filenames (alnum, dash, underscore)
        import re as _re

        if not tasklist_key or not _re.match(r"^[A-Za-z0-9_-]+$", tasklist_key):
            raise ValueError(f"Invalid tasklist key: {tasklist_key!r}")

        tl = TaskList.from_dict(tasklist) if isinstance(tasklist, dict) else tasklist

        # Enforce key == id: the tasklist id must match its storage key
        if tl.id != tasklist_key:
            tl.id = str(tasklist_key)


        path = self._tasklist_path(account_name, tasklist_key)
        self._ensure_dir(path.parent)
        self._tasklist_service.save(str(path), tl)

    def delete_tasklist(self, account_name: str, tasklist_key: str) -> None:

        path = self._tasklist_path(account_name, tasklist_key)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logging.error("Failed to delete tasklist %s: %s", path, e)
