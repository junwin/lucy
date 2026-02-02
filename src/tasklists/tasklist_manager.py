from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.storage.base import Storage
from .task_list import TaskList
from .task import Task
from .task_states import (
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_LIST_STATE_COMPLETED,
)

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskListManager:
    """Helper for creating, loading, persisting and running TaskLists.

    Responsibilities (minimal):
    - Support tasklist-level meta (supervisor_agent, worker_agent) when
      persisting tasklists. These are stored as top-level keys alongside the
      TaskList dict so existing TaskList.from_dict/from_json remain compatible.
    - Run tasklists one-by-one, persisting after each task, and support
      resuming from the last incomplete task.

    This class intentionally keeps execution "local" and does not call any
    external tooling. It is intended as a small refactor target so higher
    level processors (AutomationProcessor) can delegate execution and
    persistence to a single place.
    """

    def __init__(self, storage: Storage):
        self.storage = storage

    # -----------------
    # Persistence helpers
    # -----------------

    def _serialize_tasklist(self, tasklist: TaskList, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        d = json.loads(tasklist.to_json())
        if meta:
            # shallow copy of meta keys at top-level so older code can ignore them
            for k, v in meta.items():
                if v is not None:
                    d[k] = v
        return d

    def save_tasklist(self, account_name: str, tasklist_id: str, tasklist: TaskList, *, meta: Optional[Dict[str, Any]] = None) -> None:
        payload = self._serialize_tasklist(tasklist, meta=meta)
        self.storage.save_tasklist(account_name, tasklist_id, payload)

    def load_tasklist(self, account_name: str, tasklist_id: str) -> Tuple[Optional[TaskList], Dict[str, Any]]:
        raw = self.storage.get_tasklist(account_name, tasklist_id)
        if raw is None:
            return None, {}

        # raw may be a string (JSON) or a dict
        data: Dict[str, Any]
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except Exception:
                logger.exception("Invalid JSON tasklist in storage")
                return None, {}
        elif isinstance(raw, dict):
            data = dict(raw)
        else:
            logger.warning("Unsupported tasklist type from storage: %s", type(raw))
            return None, {}

        # extract meta fields if present
        meta_keys = ["supervisor_agent", "worker_agent"]
        meta: Dict[str, Any] = {}
        for k in meta_keys:
            if k in data:
                meta[k] = data.pop(k)

        try:
            tl = TaskList.from_dict(data)
            return tl, meta
        except Exception:
            logger.exception("Failed to parse TaskList from stored data")
            return None, meta

    # -----------------
    # Tasklist creation
    # -----------------

    def create_tasklist(self, account_name: str, tasklist_id: str, tasks: Optional[list] = None, *, supervisor_agent: Optional[str] = None, worker_agent: Optional[str] = None) -> TaskList:
        tasks = tasks or []
        # Coerce incoming task dicts into Task objects if necessary
        t_objs = []
        for i, t in enumerate(tasks, start=1):
            if isinstance(t, Task):
                t_objs.append(t)
            elif isinstance(t, dict):
                # ensure id present
                if "id" not in t:
                    t["id"] = i
                t_objs.append(Task.from_dict(t))
            else:
                raise TypeError("tasks must be Task or dict")

        tl = TaskList(id=tasklist_id, tasks=t_objs)
        meta = {"supervisor_agent": supervisor_agent, "worker_agent": worker_agent}
        self.save_tasklist(account_name, tasklist_id, tl, meta=meta)
        return tl

    # -----------------
    # Execution
    # -----------------

    def _find_next_pending_index(self, tasklist: TaskList) -> Optional[int]:
        for idx, task in enumerate(getattr(tasklist, "tasks", []) ):
            if getattr(task, "state", None) == TASK_STATE_PENDING:
                return idx
        return None

    def run_tasklist(self, account_name: str, tasklist_id: str, *, mode: str = "single-step", processor_factory: Optional[Any] = None) -> Dict[str, Any]:
        """Run or resume a persisted tasklist.

        Behavior:
        - Loads the tasklist and any meta.
        - Marks TaskList.state running when appropriate.
        - Executes one or more tasks sequentially depending on mode.
        - After completing each task, persists the tasklist (including meta).
        - Returns a small summary dict: {state, executed_count, last_task}
        """
        tasklist, meta = self.load_tasklist(account_name, tasklist_id)
        if tasklist is None:
            return {"state": "missing", "executed": 0}

        try:
            if getattr(tasklist, "state", None) == TASK_LIST_STATE_CREATED:
                tasklist.state = TASK_LIST_STATE_RUNNING
        except Exception:
            logger.exception("Failed updating tasklist state")

        executed = 0
        last_task_name = ""
        overall_state = "running"

        while True:
            idx = self._find_next_pending_index(tasklist)
            if idx is None:
                try:
                    tasklist.state = TASK_LIST_STATE_COMPLETED
                except Exception:
                    logger.exception("Failed setting tasklist completed")
                overall_state = "completed"
                break

            task = tasklist.tasks[idx]
            last_task_name = getattr(task, "title", None) or f"task#{idx}"

            try:
                task.state = TASK_STATE_RUNNING
            except Exception:
                logger.exception("Failed setting task running")

            # Placeholder execution: record timestamp and a note. Higher level
            # processors can call out to external function_calling processors if
            # needed; for Part 1+2 we keep execution local.
            try:
                task.result = {"timestamp": _now_utc(), "note": "placeholder"}
            except Exception:
                logger.exception("Failed attaching placeholder result")

            try:
                task.state = TASK_STATE_COMPLETED
            except Exception:
                logger.exception("Failed setting task completed")
                overall_state = "failed"

            executed += 1

            try:
                # Persist after each task -- include meta so info is not lost.
                self.save_tasklist(account_name, tasklist_id, tasklist, meta=meta)
            except Exception as e:
                logger.exception("Failed persisting tasklist")
                overall_state = "failed"
                return {"state": "failed", "error": str(e), "executed": executed, "last_task": last_task_name}

            if overall_state == "failed":
                break

            if mode != "multi-step":
                break

        # final persist
        try:
            self.save_tasklist(account_name, tasklist_id, tasklist, meta=meta)
        except Exception:
            logger.exception("Failed final persist")

        return {"state": overall_state, "executed": executed, "last_task": last_task_name}


# end of file
