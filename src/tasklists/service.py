from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from .task_list import TaskList
from .task_states import (
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_FAILED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_STATE_COMPLETED_WITH_ERRORS,
    TASK_STATE_FAILED,
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
)


class TaskListService:
    """Single service boundary for TaskList creation and domain normalization.

    Step 2 scope: in-memory operations only (no persistence path decisions yet).
    """

    def load(self, path: str) -> TaskList:
        """Load a TaskList from a JSON file path.

        Raises FileNotFoundError if the file does not exist.
        """

        with open(path, "r", encoding="utf-8") as f:
            return TaskList.from_json(f.read())

    def create(
        self,
        name: str,
        description: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
        general_instructions: str = "",
    ) -> TaskList:
        return TaskList(
            id=str(uuid.uuid4()),
            schema_version=1,
            state=TASK_LIST_STATE_CREATED,
            name=name,
            description=description,
            tasks=[],
            meta=meta or {},
            general_instructions=general_instructions,
        )

    def save(self, path: str, tasklist: TaskList) -> None:
        """Normalize then save to a JSON file path."""

        self._normalize(tasklist)
        with open(path, "w", encoding="utf-8") as f:
            f.write(tasklist.to_json())

    def reset(self, tasklist: TaskList) -> TaskList:
        """Mutate the tasklist back to a fresh Created/Pending state."""

        tasklist.state = TASK_LIST_STATE_CREATED
        tasklist.current_task_id = None
        for t in tasklist.tasks:
            t.state = TASK_STATE_PENDING
            t.result = None
            t.error = None
            t.run_metrics = None
        return tasklist

    def _normalize(self, tasklist: TaskList) -> None:
        """Recompute tasklist.state from task states.

        Rules:
        - zero tasks -> Created
        - all tasks Pending -> Created (not started)
        - any task Failed -> Failed
        - any task Running OR mix of states -> Running
        - all tasks Completed -> Completed
        """

        tasks = list(tasklist.tasks or [])
        if len(tasks) == 0:
            tasklist.state = TASK_LIST_STATE_CREATED
            return

        states = [t.state for t in tasks]

        if all(s == TASK_STATE_PENDING for s in states):
            tasklist.state = TASK_LIST_STATE_CREATED
            return

        if any(s in (TASK_STATE_FAILED, TASK_STATE_COMPLETED_WITH_ERRORS) for s in states):
            tasklist.state = TASK_LIST_STATE_FAILED
            return

        if any(s == TASK_STATE_RUNNING for s in states):
            tasklist.state = TASK_LIST_STATE_RUNNING
            return

        if all(s == TASK_STATE_COMPLETED for s in states):
            tasklist.state = TASK_LIST_STATE_COMPLETED
            return

        # Any mix (e.g. Completed + Pending) counts as Running per John.
        tasklist.state = TASK_LIST_STATE_RUNNING
