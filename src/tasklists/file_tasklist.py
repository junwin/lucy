from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .tasklist_interface import (
    AbstractTask,
    AbstractTaskList,
    TASK_LIST_STATE_CREATED,
    TASK_STATE_PENDING,
)


@dataclass
class FileTask(AbstractTask):
    task_id: str
    description: str
    state: str = TASK_STATE_PENDING
    result: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self, *, indent: Optional[int] = None) -> str:
        return json.dumps(
            {
                "task_id": self.task_id,
                "description": self.description,
                "state": self.state,
                "result": self.result,
                "extra": self.extra,
            },
            indent=indent,
        )

    @classmethod
    def from_json(cls, s: str) -> "FileTask":
        data = json.loads(s)
        return cls(
            task_id=data["task_id"],
            description=data.get("description", ""),
            state=data.get("state", TASK_STATE_PENDING),
            result=data.get("result"),
            extra=data.get("extra", {}) or {},
        )


class FileTaskList(AbstractTaskList):
    def __init__(
        self,
        task_list_id: str,
        state: str = TASK_LIST_STATE_CREATED,
        _title: str = "",
        _description: str = "",
        _tasks: Optional[List[FileTask]] = None,
    ):
        self.task_list_id = task_list_id
        self.state = state
        self._title = _title
        self._description = _description
        self._tasks: List[FileTask] = list(_tasks or [])

    # ---- metadata ----

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    # ---- task access ----

    def tasks(self) -> Iterable[AbstractTask]:
        return list(self._tasks)

    def get_task(self, task_id: str) -> Optional[AbstractTask]:
        for t in self._tasks:
            if t.task_id == task_id:
                return t
        return None

    def add_task(self, task: AbstractTask) -> None:
        # Replace by id if present, preserving position.
        for i, existing in enumerate(self._tasks):
            if existing.task_id == task.task_id:
                self._tasks[i] = task  # type: ignore[assignment]
                return
        self._tasks.append(task)  # type: ignore[arg-type]

    def update_task_state(self, task_id: str, new_state: str) -> None:
        t = self.get_task(task_id)
        if t is None:
            return
        t.state = new_state

    def set_task_result(
        self,
        task_id: str,
        result: str,
        *,
        new_state: Optional[str] = None,
    ) -> None:
        t = self.get_task(task_id)
        if t is None:
            return
        t.result = result
        if new_state is not None:
            t.state = new_state

    # ---- serialisation ----

    def to_json(self, *, indent: Optional[int] = None) -> str:
        payload = {
            "task_list_id": self.task_list_id,
            "state": self.state,
            "title": self.title,
            "description": self.description,
            "tasks": [json.loads(t.to_json()) for t in self._tasks],
        }
        return json.dumps(payload, indent=indent)

    @classmethod
    def from_json(cls, s: str) -> "FileTaskList":
        data = json.loads(s)
        tasks = [FileTask.from_json(json.dumps(t)) for t in data.get("tasks", [])]
        return cls(
            task_list_id=data["task_list_id"],
            state=data.get("state", TASK_LIST_STATE_CREATED),
            _title=data.get("title", ""),
            _description=data.get("description", ""),
            _tasks=tasks,
        )


# ---- file helpers ----

def save_tasklist_to_file(tasklist: FileTaskList, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(tasklist.to_json(indent=2))


def load_tasklist_from_file(path: str) -> FileTaskList:
    with open(path, "r", encoding="utf-8") as f:
        return FileTaskList.from_json(f.read())
