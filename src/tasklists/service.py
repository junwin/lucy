from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .interfaces import TasklistManager
from .task import Task
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

if TYPE_CHECKING:
    from src.storage.interfaces import TasklistStore


class TaskListService(TasklistManager):
    """CRUD facade over an injected TasklistStore persistence port."""

    def __init__(self, store: TasklistStore):
        self.store = store

    def list(self, account_name: str) -> List[str]:
        return self.store.list_tasklists(account_name)

    def get(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        return self.store.get_tasklist(account_name, tasklist_key)

    def save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        self.store.save_tasklist(account_name, tasklist_key, tasklist)

    def delete(self, account_name: str, tasklist_key: str) -> None:
        self.store.delete_tasklist(account_name, tasklist_key)

    def create(
        self,
        tasklist_key: str,
        name: str,
        description: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
        general_instructions: str = "",
    ) -> TaskList:
        return TaskList(
            id=tasklist_key,
            schema_version=1,
            state=TASK_LIST_STATE_CREATED,
            name=name,
            description=description,
            tasks=[],
            meta=meta or {},
            general_instructions=general_instructions,
        )

    def create_from_goal(
        self,
        tasklist_key: str,
        goal: str,
        files: Optional[List[str]] = None,
        worker_agent: Optional[str] = None,
    ) -> TaskList:
        name = tasklist_key.replace("-", " ").replace("_", " ").title()
        tasklist = TaskList(
            id=tasklist_key,
            schema_version=1,
            state=TASK_LIST_STATE_CREATED,
            name=name,
            description=goal,
            tasks=[],
            meta={},
            general_instructions=goal,
        )
        if files:
            for i, filepath in enumerate(files):
                fname = os.path.basename(filepath)
                task_name = os.path.splitext(fname)[0]
                tasklist.add_task(
                    Task(
                        id=f"task-{i + 1}",
                        name=task_name,
                        instructions=goal,
                        agent=worker_agent,
                    )
                )
        else:
            tasklist.add_task(
                Task(
                    id="task-1",
                    name="Execute goal",
                    instructions=goal,
                    agent=worker_agent,
                )
            )
        return tasklist

    def add_task(
        self,
        account_name: str,
        tasklist_key: str,
        task: Task,
        *,
        after_index: Optional[int] = None,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.add_task(task, after_index=after_index)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def update_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        **changes: Any,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.update_task(task_id, **changes)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def remove_task(self, account_name: str, tasklist_key: str, task_id: str) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.remove_task(task_id)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_state(self, account_name: str, tasklist_key: str, state: str) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.state = str(state)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_name(self, account_name: str, tasklist_key: str, name: str) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.name = str(name)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_description(self, account_name: str, tasklist_key: str, description: str) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.description = str(description)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_general_instructions(
        self, account_name: str, tasklist_key: str, instructions: str
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.general_instructions = str(instructions)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def update_meta(
        self, account_name: str, tasklist_key: str, meta: Dict[str, Any]
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        if not isinstance(meta, dict):
            raise TypeError("meta must be a dict")
        tl.meta.update(meta)
        self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def _load_required(self, account_name: str, tasklist_key: str) -> TaskList:
        tl = self.store.get_tasklist(account_name, tasklist_key)
        if tl is None:
            raise ValueError(f"tasklist '{tasklist_key}' not found")
        return tl

    def load(self, path: str) -> TaskList:
        """Load a TaskList from a JSON file path.

        Raises FileNotFoundError if the file does not exist.
        """

        with open(path, "r", encoding="utf-8") as f:
            return TaskList.from_json(f.read())

    def save_file(self, path: str, tasklist: TaskList) -> None:
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
            t.error = None
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
