from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
import json
import uuid

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


@dataclass
class TaskList:
    # id is required in-memory and always persisted in to_dict
    id: str
    # bump schema version for the new Task shape (Task.id is a UUID string)
    schema_version: int = 2
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Task] = field(default_factory=list)
    # Arbitrary metadata for callers (agent/session info, etc.)
    meta: Dict[str, Any] = field(default_factory=dict)
    # optional pointer to the current running task id (UUID string)
    current_task_id: Optional[str] = None

    # -----------------
    # Domain behavior
    # -----------------

    def task_list(self) -> Iterable[Task]:
        return list(self.tasks)

    def get_task(self, id: str) -> Optional[Task]:
        """Return a task by its id (UUID string).

        Note: older code used integer ids; callers should pass the UUID
        string form. Comparison is done as string equality.
        """
        for t in self.tasks:
            if str(t.id) == str(id):
                return t
        return None

    def next_id(self) -> str:
        """Generate a new UUID string suitable for Task.id.

        Previously integer ids were used; new Task ids are UUID strings.
        """
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
        """Serialize TaskList -> plain dict (suitable for JSON encoding).

        Prefer this over to_json() in storage/boundary layers.
        """
        if not getattr(self, "id", None):
            raise ValueError("TaskList.id is required for serialization")

        d: Dict[str, Any] = {
            "schema_version": int(self.schema_version),
            "id": str(self.id),
            "state": self.state,
            "tasks": [task.to_dict() for task in self.tasks],
        }

        # Persist/round-trip arbitrary metadata (agent/session info, etc.)
        # Always include it to keep the boundary stable.
        d["meta"] = dict(self.meta or {})
        if self.current_task_id is not None:
            d["current_task_id"] = str(self.current_task_id)

        return d

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        id: Optional[str] = None,
        *,
        allow_legacy_meta: bool = False,
    ) -> "TaskList":
        """Deserialize plain dict -> TaskList.

        Rules:
        - Accept schema_version 2 (current). If absent, default to 2.
        - Support migration from schema_version 1 (legacy): title->instructions,
          int id->uuid, status->state. Unknown task-level keys are moved into
          task.meta only if allow_legacy_meta is True; otherwise the loader
          will raise.
        - The resulting TaskList must have an id. If the input dict does not
          include an 'id', the caller may provide one via the `id` parameter.
          Otherwise a ValueError is raised.
        """
        if not isinstance(data, dict):
            raise TypeError("TaskList.from_dict expects a dict")

        sv = data.get("schema_version", 2)
        if sv is None:
            sv = 2
        try:
            sv = int(sv)
        except Exception:
            raise ValueError("Invalid schema_version")
        # Support v1 -> v2 migration. v2 is the current shape.
        if sv not in (1, 2):
            raise ValueError(f"Unsupported TaskList schema_version: {sv}")

        # determine id
        id_in_data = data.get("id")
        final_id = None
        if id_in_data is not None:
            final_id = str(id_in_data)
        elif id is not None:
            final_id = str(id)
        else:
            raise ValueError("TaskList id is required (provide in dict or via id=)")

        # Handle migration from v1: map legacy keys and convert task ids
        tasks_input = data.get("tasks", [])
        tasks: List[Task] = []
        if sv == 1:
            # v1 used 'status'/'title' and numeric ids possibly. Use Task.from_dict
            # which knows how to migrate legacy task shape. We only allow moving
            # unknown task-level keys into meta if allow_legacy_meta is True.
            for t in tasks_input:
                tasks.append(Task.from_dict(t, allow_legacy=True, allow_legacy_meta=allow_legacy_meta))
        else:
            for t in tasks_input:
                tasks.append(Task.from_dict(t))

        meta = data.get("meta", {})
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ValueError("meta must be a dict")

        current_task_id = data.get("current_task_id")
        if current_task_id is not None:
            current_task_id = str(current_task_id)

        return cls(
            id=final_id,
            schema_version=sv,
            state=data.get("state", TASK_LIST_STATE_CREATED),
            tasks=tasks,
            meta=meta,
            current_task_id=current_task_id,
        )

    def to_json(self) -> str:
        """Serialize TaskList -> JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        """Deserialize JSON string -> TaskList."""
        data = json.loads(json_str)
        return cls.from_dict(data)
