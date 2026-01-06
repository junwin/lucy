from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .task_runner import PlannedTaskList
from .tasklist_interface import (
    AbstractTask,
    AbstractTaskList,
    TASK_LIST_STATE_CREATED,
    TASK_STATE_PENDING,
)


@dataclass
class FileTask(AbstractTask):
    """Concrete task implementation backed by simple in-memory fields.

    This is serialisable to/from dict/JSON and suitable for use in a
    FileTaskList.
    """

    task_id: str
    description: str
    state: str = TASK_STATE_PENDING
    result: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "state": self.state,
            "result": self.result,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileTask":
        return cls(
            task_id=data["task_id"],
            description=data.get("description", ""),
            state=data.get("state", TASK_STATE_PENDING),
            result=data.get("result"),
            extra=data.get("extra") or {},
        )


@dataclass
class FileTaskList(AbstractTaskList):
    """Concrete task list implementation that keeps tasks in memory and
    can be serialised to/from a single JSON string.

    This is suitable for storing the JSON string in a node.info field or
    persisting it to disk.
    """

    task_list_id: str
    state: str = TASK_LIST_STATE_CREATED
    _title: str = ""
    _description: str = ""
    _tasks: List[FileTask] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_planned_tasklist(
        cls,
        planned: PlannedTaskList,
        *,
        task_list_id: str,
        state: str = TASK_LIST_STATE_CREATED,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "FileTaskList":
        """Create a FileTaskList from a canonical PlannedTaskList.

        Mapping rules:
        - FileTask.description is the task title.
        - The worker instruction text is preserved in FileTask.extra['instruction'].
        """

        tasks: List[FileTask] = []
        for t in planned.tasks:
            tasks.append(
                FileTask(
                    task_id=t.id,
                    description=t.title or "",
                    extra={
                        "instruction": t.instruction,
                        "agent": t.agent,
                        "file": t.file,
                        "type": t.type,
                        "params": t.params,
                    },
                )
            )

        return cls(
            task_list_id=task_list_id,
            state=state,
            _title=planned.description or "",
            _description=planned.description or "",
            _tasks=tasks,
            extra=extra or {},
        )

    # ---- metadata ----

    @property
    def title(self) -> str:  # type: ignore[override]
        return self._title

    @title.setter
    def title(self, value: str) -> None:  # type: ignore[override]
        self._title = value

    @property
    def description(self) -> str:  # type: ignore[override]
        return self._description

    @description.setter
    def description(self, value: str) -> None:  # type: ignore[override]
        self._description = value

    # ---- task access ----

    def tasks(self) -> Iterable[FileTask]:  # type: ignore[override]
        """Return a shallow copy of the tasks list to avoid external mutation."""
        return list(self._tasks)

    def get_task(self, task_id: str) -> Optional[FileTask]:  # type: ignore[override]
        for task in self._tasks:
            if task.task_id == task_id:
                return task
        return None

    def add_task(self, task: FileTask) -> None:  # type: ignore[override]
        """Add a task, replacing any existing task with the same id."""
        for idx, existing in enumerate(self._tasks):
            if existing.task_id == task.task_id:
                self._tasks[idx] = task
                return
        self._tasks.append(task)

    def update_task_state(self, task_id: str, new_state: str) -> None:  # type: ignore[override]
        task = self.get_task(task_id)
        if task is not None:
            task.state = new_state

    def set_task_result(
        self,
        task_id: str,
        result: str,
        *,
        new_state: Optional[str] = None,
    ) -> None:  # type: ignore[override]
        task = self.get_task(task_id)
        if task is not None:
            task.result = result
            if new_state is not None:
                task.state = new_state

    # ---- serialisation ----

    def to_dict(self) -> Dict[str, Any]:  # type: ignore[override]
        return {
            "task_list_id": self.task_list_id,
            "state": self.state,
            "title": self._title,
            "description": self._description,
            "tasks": [t.to_dict() for t in self._tasks],
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileTaskList":  # type: ignore[override]
        tasks_data = data.get("tasks") or []
        tasks = [FileTask.from_dict(t) for t in tasks_data]

        return cls(
            task_list_id=data["task_list_id"],
            state=data.get("state", TASK_LIST_STATE_CREATED),
            _title=data.get("title", ""),
            _description=data.get("description", ""),
            _tasks=tasks,
            extra=data.get("extra") or {},
        )

    def to_json(self, *, indent: Optional[int] = None) -> str:  # type: ignore[override]
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, s: str) -> "FileTaskList":  # type: ignore[override]
        data = json.loads(s)
        return cls.from_dict(data)


def save_tasklist_to_file(tasklist: FileTaskList, path: str) -> None:
    """Persist a task list to a file as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(tasklist.to_json(indent=2))


def load_tasklist_from_file(path: str) -> FileTaskList:
    """Load a task list from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return FileTaskList.from_json(f.read())
