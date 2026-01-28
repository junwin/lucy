from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
import json

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


@dataclass
class TaskList:
    # id is required in-memory and always persisted in to_dict
    id: str
    schema_version: int = 1
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Task] = field(default_factory=list)

    # -----------------
    # Domain behavior
    # -----------------

    def task_list(self) -> Iterable[Task]:
        return list(self.tasks)

    def get_task(self, id: int) -> Optional[Task]:
        for t in self.tasks:
            if t.id == id:
                return t
        return None

    def next_id(self) -> int:
        if not self.tasks:
            return 1
        return max(t.id for t in self.tasks) + 1

    def add_task(self, task: Task) -> None:
        for i, existing in enumerate(self.tasks):
            if existing.id == task.id:
                self.tasks[i] = task
                return
        self.tasks.append(task)

    def update_task_state(self, id: int, new_state: str) -> None:
        t = self.get_task(id)
        if t:
            t.state = new_state

    def set_task_result(
        self,
        id: int,
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

        return {
            "schema_version": int(self.schema_version),
            "id": str(self.id),
            "state": self.state,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList":
        """Deserialize plain dict -> TaskList.

        Rules:
        - Accept only schema_version == 1. If absent, default to 1.
        - The resulting TaskList must have an id. If the input dict does not
          include an 'id', the caller may provide one via the `id` parameter.
          Otherwise a ValueError is raised.
        """
        if not isinstance(data, dict):
            raise TypeError("TaskList.from_dict expects a dict")

        sv = data.get("schema_version", 1)
        if sv is None:
            sv = 1
        try:
            sv = int(sv)
        except Exception:
            raise ValueError("Invalid schema_version")
        if sv != 1:
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

        tasks = [Task.from_dict(task_dict) for task_dict in data.get("tasks", [])]

        return cls(
            id=final_id,
            schema_version=sv,
            state=data.get("state", TASK_LIST_STATE_CREATED),
            tasks=tasks,
        )

    def to_json(self) -> str:
        """Serialize TaskList -> JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        """Deserialize JSON string -> TaskList."""
        data = json.loads(json_str)
        return cls.from_dict(data)
