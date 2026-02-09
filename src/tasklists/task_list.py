from __future__ import annotations
from .task_states import TASK_LIST_STATE_CREATED


import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field as PField, TypeAdapter, ValidationError  # type: ignore
    _HAS_PYDANTIC = True
except Exception:
    _HAS_PYDANTIC = False

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


# --- Optional: Pydantic boundary model (module-level, not inside methods) ---
if _HAS_PYDANTIC:
    class _TaskListModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        schema_version: int = 2
        id: uuid.UUID
        state: str = TASK_LIST_STATE_CREATED
        tasks: List[Dict[str, Any]] = PField(default_factory=list)  # validate task dicts; Task handles its own schema
        meta: Dict[str, Any] = PField(default_factory=dict)
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
            # canonicalize if provided
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
        if not getattr(self, "id", None):
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

        # If pydantic is available, validate the *TaskList envelope* strictly
        if _HAS_PYDANTIC:
            try:
                validated = _TASKLIST_ADAPTER.validate_python(payload)
            except ValidationError as exc:
                raise ValueError(f"TaskList validation error: {exc}") from exc

            # Validate tasks using Task.from_dict (which is already strict)
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

        # Fallback (no pydantic)
        sv = payload.get("schema_version", 2) or 2
        sv = int(sv)
        if sv != 2:
            raise ValueError(f"Unsupported TaskList schema_version: {sv}")

        final_id = payload.get("id")
        if final_id is None:
            raise ValueError("TaskList id is required (provide in dict or via id=)")

        tasks_input = payload.get("tasks", [])
        if tasks_input is None:
            tasks_input = []
        if not isinstance(tasks_input, list):
            raise ValueError("tasks must be a list")

        tasks: List[Task] = [Task.from_dict(t) for t in tasks_input]

        meta = payload.get("meta", {}) or {}
        if not isinstance(meta, dict):
            raise ValueError("meta must be a dict")

        current_task_id = payload.get("current_task_id")
        if current_task_id is not None:
            current_task_id = str(current_task_id)

        return cls(
            id=str(final_id),
            schema_version=sv,
            state=payload.get("state", TASK_LIST_STATE_CREATED),
            tasks=tasks,
            meta=meta,
            current_task_id=current_task_id,
            name=payload.get("name"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        data = json.loads(json_str)
        return cls.from_dict(data)
