from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, field_validator

from .task import Task, _TaskModel
from .task_states import TASK_LIST_STATE_CREATED, TASK_STATE_PENDING

_TASK_UPDATABLE_FIELDS = frozenset(
    {
        "name",
        "instructions",
        "state",
        "error",
        "meta",
        "agent",
        "position",
        "parent_id",
        "files",
    }
)


class _TaskListModel(BaseModel):
    schema_version: int
    id: str
    name: str
    description: str
    general_instructions: str = ""
    state: Optional[str] = TASK_LIST_STATE_CREATED
    tasks: List[_TaskModel] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    current_task_id: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def check_schema_version(cls, v):
        try:
            if int(v) != 1:
                raise ValueError("schema_version must be 1")
        except Exception:
            raise ValueError("schema_version must be an int equal to 1")
        return int(v)


@dataclass
class TaskList:
    id: str
    name: str
    description: str
    schema_version: int = 1
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Task] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    general_instructions: str = ""

    def __post_init__(self) -> None:
        # Keep id flexible for readers/tests. Persist IDs as strings but
        # avoid strict UUID normalization on read/creation. Normalization
        # and stricter validation are the responsibility of the storage/PUT
        # path.
        self.id = str(self.id)

        # Enforce schema_version == 1
        try:
            self.schema_version = int(self.schema_version)
        except Exception as exc:
            raise TypeError("TaskList.schema_version must be an int") from exc
        if self.schema_version != 1:
            raise ValueError(f"Unsupported TaskList schema_version: {self.schema_version}")

        if not self.name:
            raise ValueError("TaskList.name is required")
        if not self.description:
            raise ValueError("TaskList.description is required")

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
            # keep as string
            self.current_task_id = str(self.current_task_id)

        if self.general_instructions is None:
            self.general_instructions = ""
        if not isinstance(self.general_instructions, str):
            raise TypeError("TaskList.general_instructions must be a str")

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

    def add_task(self, task: Task, *, after_index: Optional[int] = None) -> None:
        for existing in self.tasks:
            if existing.id == task.id:
                raise ValueError(f"task with id '{task.id}' already exists")
        if after_index is None:
            self.tasks.append(task)
            return
        index = int(after_index)
        if index < 0:
            raise ValueError(f"after_index must be >= 0, got {after_index}")
        self.tasks.insert(min(index + 1, len(self.tasks)), task)

    def update_task(self, id: str, **changes: Any) -> None:
        unknown = set(changes) - _TASK_UPDATABLE_FIELDS
        if unknown:
            fields = ", ".join(sorted(unknown))
            raise ValueError(f"cannot update task field(s): {fields}")
        t = self.get_task(id)
        if t is None:
            raise ValueError(f"task with id '{id}' not found")
        if "name" in changes:
            t.name = str(changes["name"])
        if "instructions" in changes:
            t.instructions = str(changes["instructions"])
        if "state" in changes:
            t.state = changes["state"] or TASK_STATE_PENDING
        if "error" in changes:
            t.error = changes["error"]
        if "meta" in changes:
            if not isinstance(changes["meta"], dict):
                raise TypeError("task meta must be a dict")
            t.meta.update(changes["meta"])
        if "agent" in changes:
            t.agent = changes["agent"]
        if "position" in changes:
            t.position = changes["position"]
        if "parent_id" in changes:
            t.parent_id = changes["parent_id"]
        if "files" in changes:
            t.files = list(changes["files"] or [])

    def remove_task(self, id: str) -> None:
        for i, t in enumerate(self.tasks):
            if str(t.id) == str(id):
                self.tasks.pop(i)
                return
        raise ValueError(f"task with id '{id}' not found")

    def update_task_state(self, id: str, new_state: str) -> None:
        t = self.get_task(id)
        if t is None:
            raise ValueError(f"task with id '{id}' not found")
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
        if t is None:
            raise ValueError(f"task with id '{id}' not found")
        t.result = result
        if error is not None:
            t.error = error
        if new_state is not None:
            t.state = new_state

    def get_children(self, parent_id: str) -> List[Task]:
        """
        Return all tasks whose parent_id equals the provided parent_id.
        This is a simple filter (no ordering or execution logic).
        If there are no matching children, returns an empty list.
        """
        return [t for t in self.tasks if t.parent_id == parent_id]

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
            "name": str(self.name),
            "description": str(self.description),
            "tasks": [task.to_dict() for task in self.tasks],
            "meta": dict(self.meta or {}),
        }
        # include current_task_id only if present
        if self.current_task_id is not None:
            d["current_task_id"] = str(self.current_task_id)
        # include general_instructions only when non-empty to maintain backward compatibility
        if self.general_instructions:
            d["general_instructions"] = str(self.general_instructions)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList":
        if not isinstance(data, dict):
            raise TypeError("TaskList.from_dict expects a dict")

        payload = dict(data)
        if id is not None and "id" not in payload:
            payload["id"] = id

        try:
            validated = _TaskListModel.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"TaskList.validation error: {exc}") from exc

        # Build Task domain objects from validated tasks
        tasks: List[Task] = []
        for t in validated.tasks:
            # t is an instance of _TaskModel
            tasks.append(
                Task(
                    id=t.id,
                    name=t.name,
                    instructions=t.instructions,
                    state=t.state or None,
                    result=t.result,
                    error=t.error,
                    meta=t.meta,
                    agent=t.agent,
                    position=getattr(t, "position", None),
                    files=getattr(t, "files", []) or [],
                    parent_id=getattr(t, "parent_id", None),
                    run_metrics=getattr(t, "run_metrics", None),
                    context=getattr(t, "context", None),
                )
            )

        seen: set = set()
        for t in tasks:
            if t.id in seen:
                raise ValueError(f"duplicate task id '{t.id}' in tasklist data")
            seen.add(t.id)

        return cls(
            id=str(validated.id),
            schema_version=int(validated.schema_version),
            state=str(validated.state) if validated.state is not None else TASK_LIST_STATE_CREATED,
            tasks=tasks,
            meta=dict(validated.meta or {}),
            current_task_id=str(validated.current_task_id) if validated.current_task_id else None,
            name=str(validated.name),
            description=str(validated.description),
            general_instructions=str(validated.general_instructions) if validated.general_instructions is not None else "",
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        return cls.from_dict(json.loads(json_str))
