from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import List, Optional

from src.tasklists import TaskList

from .tasklist_runs import TaskExecutionReader, TaskExecutionRecorder


DEFAULT_RUN_TTL_DAYS = 2


class TasklistsMixin:
    """Tasklist methods extracted from JsonFileStorage.

    Mixin: relies on self.storage_paths and self._ensure_dir provided by
    the composing class.
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

    def _tasklist_runs_path(self, account_name: str, tasklist_key: str) -> Path:
        rel = f"tasklists/{account_name}/{tasklist_key}.runs.jsonl"
        return self.storage_paths.resolve_relative(rel)

    def list_tasklists(self, account_name: str) -> List[str]:
        d = self._tasklists_dir(account_name)
        if not d.exists() or not d.is_dir():
            return []

        ids: List[str] = []
        for p in d.glob("*.json"):
            ids.append(p.stem)

        ttl_days = getattr(self, "_tasklist_run_ttl_days", DEFAULT_RUN_TTL_DAYS)
        for runs_file in d.glob("*.runs.jsonl"):
            try:
                if time.time() - runs_file.stat().st_mtime > ttl_days * 86400:
                    runs_file.unlink()
            except Exception as e:
                logging.error("Failed to sweep runs file %s: %s", runs_file, e)

        ids.sort()
        return ids

    def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        """Load a tasklist from its JSON file; None if the file is missing."""

        path = self._tasklist_path(account_name, tasklist_key)
        try:
            return TaskList.from_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        """Persist a tasklist as its JSON file."""

        # Basic id validation: only allow simple filenames (alnum, dash, underscore)
        import re as _re

        if not tasklist_key or not _re.match(r"^[A-Za-z0-9_-]+$", tasklist_key):
            raise ValueError(f"Invalid tasklist key: {tasklist_key!r}")

        tl = TaskList.from_dict(tasklist) if isinstance(tasklist, dict) else tasklist

        # Enforce key == id: the tasklist id must match its storage key
        if tl.id != tasklist_key:
            tl.id = str(tasklist_key)

        legacy_tasks = [t for t in tl.tasks if t.result is not None or t.run_metrics is not None]
        if legacy_tasks:
            runs_path = self._tasklist_runs_path(account_name, tasklist_key)
            self._ensure_dir(runs_path.parent)
            for task in legacy_tasks:
                TaskExecutionRecorder.append(
                    runs_path,
                    {
                        "schema_version": 1,
                        "record_id": uuid.uuid4().hex,
                        "tasklist_key": tasklist_key,
                        "task_id": task.id,
                        "task_name": task.name,
                        "state": task.state,
                        "error": task.error,
                        "legacy": True,
                        "result": task.result,
                        "run_metrics": task.run_metrics,
                    },
                )
                task.result = None
                task.run_metrics = None

        path = self._tasklist_path(account_name, tasklist_key)
        self._ensure_dir(path.parent)
        path.write_text(tl.to_json(), encoding="utf-8")

    def delete_tasklist(self, account_name: str, tasklist_key: str) -> None:

        path = self._tasklist_path(account_name, tasklist_key)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logging.error("Failed to delete tasklist %s: %s", path, e)

        runs_path = self._tasklist_runs_path(account_name, tasklist_key)
        try:
            if runs_path.exists():
                runs_path.unlink()
        except Exception as e:
            logging.error("Failed to delete tasklist runs file %s: %s", runs_path, e)

    def append_task_execution_record(self, account_name: str, tasklist_key: str, record: dict) -> None:
        """Append one task execution record to the tasklist's runs file."""
        runs_path = self._tasklist_runs_path(account_name, tasklist_key)
        self._ensure_dir(runs_path.parent)
        TaskExecutionRecorder.append(runs_path, record)

    def get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict]:
        """Return the latest execution record for a task, else legacy inline content."""
        tasklist = self.get_tasklist(account_name, tasklist_key)
        if tasklist is None:
            return None
        runs_path = self._tasklist_runs_path(account_name, tasklist_key)
        record = TaskExecutionReader.latest(runs_path, task_id)
        if record is not None:
            return record
        task = tasklist.get_task(task_id)
        if task is None:
            return None
        if task.result is not None or task.run_metrics is not None:
            return {
                "legacy": True,
                "task_id": task.id,
                "state": task.state,
                "error": task.error,
                "result": task.result,
                "run_metrics": task.run_metrics,
            }
        return None
