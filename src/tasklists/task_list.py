from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


class _TaskListModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    id: uuid.UUID
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Dict[str, Any]] = Field(default_factory=list)  # Task.from_dict validates each
    meta: Dict[str, Any] = Field(default_factory=dict)
    current_task_id: Optional[uuid.UUID] = None
    name: Optional[str] = None


_TASKLIST_ADAPTER = TypeAdapter(_TaskListModel)


@dataclass
class TaskList:
    id: str
    schema_version: int = 2
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Task] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    name: Optional[str] = None

    def __post_init__(self) -> None:
        # Normalize and validate id
        try:
            uid = self.id if isinstance(self.id, uuid.UUID) else uuid.UUID(str(self.id))
            self.id = str(uid)
        except Exception as exc:
            raise TypeError("TaskList.id must be a valid UUID string or uuid.UUID") from exc

        # Enforce schema_version == 2
        try:
            self.schema_version = int(self.schema_version)
        except Exception as exc:
            raise TypeError("TaskList.schema_version must be an int") from exc
        if self.schema_version != 2:
            raise ValueError(f"Unsupported TaskList schema_version: {self.schema_version}")

        # Normalize meta/tasks/current_task_id
        if self.meta is None:
            self.meta = {}
        if not isinstance(self.meta, dict):
            raise TypeError("TaskList.meta must be a dict")

        if self.tasks is None:
            self.tasks = []
        if not isinstance(self.tasks, list):
            raise TypeError("TaskList.tasks must be a list")

        if self.current_task_id is not None:
            try:
                self.current_task_id = str(uuid.UUID(str(self.current_task_id)))
            except Exception as exc:
                raise TypeError("TaskList.current_task_id must be a valid UUID string or uuid.UUID") from exc

    # -----------------
    # Domain behavior
    # -----------------

    def task_list(self) -> Iterable[Task]:
        return list(self.tasks)

    def get_task(self, id: str) -> Optional[Task]:
        for t in self.tasks:
            if str(t.id) == str(id):
                return t
        return None

    def next_id(self) -> str:
        return str(uuid.uuid4())

    def add_task(self, task: Task) -> None:
        for i, existing in enumerate(self.tasks):
            if existing.id == task.id:
                self.tasks[i] = task
                return
        self.tasks.append(task)

    def update_task_state(self, id: str, new_state: str) -> None:
        t = self.get_task(id)
        if t:
            t.state = new_state

    def set_task_result(
        self,
        id: str,
        result: Dict[str, Any],
        *,
        new_state: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        t = self.get_task(id)
        if not t:
            return
        t.result = result
        if error is not None:
            t.error = error
        if new_state is not None:
            t.state = new_state

    # -----------------
    # Persistence
    # -----------------

    def to_dict(self) -> Dict[str, Any]:
        if not self.id:
            raise ValueError("TaskList.id is required for serialization")

        d: Dict[str, Any] = {
            "schema_version": int(self.schema_version),
            "id": str(self.id),
            "state": self.state,
            "tasks": [task.to_dict() for task in self.tasks],
            "meta": dict(self.meta or {}),
        }
        if self.current_task_id is not None:
            d["current_task_id"] = str(self.current_task_id)
        if self.name is not None:
            d["name"] = str(self.name)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList":
        if not isinstance(data, dict):
            raise TypeError("TaskList.from_dict expects a dict")

        payload = dict(data)
        if id is not None and "id" not in payload:
            payload["id"] = id

        try:
            validated = _TASKLIST_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise ValueError(f"TaskList validation error: {exc}") from exc

        tasks: List[Task] = [Task.from_dict(t) for t in validated.tasks]

        return cls(
            id=str(validated.id),
            schema_version=int(validated.schema_version),
            state=str(validated.state),
            tasks=tasks,
            meta=dict(validated.meta or {}),
            current_task_id=str(validated.current_task_id) if validated.current_task_id else None,
            name=validated.name,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        return cls.from_dict(json.loads(json_str))
