from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .interfaces import TasklistManager
from .task import Task
from .task_list import TaskList
from .task_states import (
    TASK_LIST_STATE_CREATED,
    TASK_STATE_PENDING,
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

    def get_task_result(
        self, account_name: str, tasklist_key: str, task_id: str
    ) -> Optional[dict]:
        return self.store.get_task_result(account_name, tasklist_key, task_id)

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
        *,
        task_id: str,
        task_name: str,
        task_instructions: str = "",
        task_state: Optional[str] = None,
        task_agent: Optional[str] = None,
        task_meta: Optional[Dict[str, Any]] = None,
        task_position: Optional[int] = None,
        task_parent_id: Optional[str] = None,
        task_files: Optional[List[str]] = None,
        after_index: Optional[int] = None,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        task = Task(
            id=task_id,
            name=task_name,
            instructions=task_instructions,
            state=task_state,
            agent=task_agent,
            meta=task_meta,
            position=task_position,
            parent_id=task_parent_id,
            files=task_files,
        )
        tl.add_task(task, after_index=after_index)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def update_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        *,
        validate_only: bool = False,
        **changes: Any,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.update_task(task_id, **changes)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def remove_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.remove_task(task_id)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_state(
        self,
        account_name: str,
        tasklist_key: str,
        state: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.state = str(state)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_name(
        self,
        account_name: str,
        tasklist_key: str,
        name: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.name = str(name)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_description(
        self,
        account_name: str,
        tasklist_key: str,
        description: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.description = str(description)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def set_general_instructions(
        self,
        account_name: str,
        tasklist_key: str,
        instructions: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        tl.general_instructions = str(instructions)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def update_meta(
        self,
        account_name: str,
        tasklist_key: str,
        meta: Dict[str, Any],
        *,
        validate_only: bool = False,
    ) -> TaskList:
        tl = self._load_required(account_name, tasklist_key)
        if not isinstance(meta, dict):
            raise TypeError("meta must be a dict")
        tl.meta.update(meta)
        if not validate_only:
            self.store.save_tasklist(account_name, tasklist_key, tl)
        return tl

    def _load_required(self, account_name: str, tasklist_key: str) -> TaskList:
        tl = self.store.get_tasklist(account_name, tasklist_key)
        if tl is None:
            raise ValueError(f"tasklist '{tasklist_key}' not found")
        return tl

    def reset(self, tasklist: TaskList) -> TaskList:
        """Mutate the tasklist back to a fresh Created/Pending state."""

        tasklist.state = TASK_LIST_STATE_CREATED
        tasklist.current_task_id = None
        for t in tasklist.tasks:
            t.state = TASK_STATE_PENDING
            t.error = None
        return tasklist
