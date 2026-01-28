from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional
import json

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


@dataclass
class TaskList:
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
    # Persistence (bone-headed)
    # -----------------

    def to_json(self) -> str:
        """
        Serialize TaskList → JSON string.
        """
        data = {
            "schema_version": self.schema_version,
            "state": self.state,
            "tasks": [asdict(task) for task in self.tasks],
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        """
        Deserialize JSON string → TaskList.
        """
        data = json.loads(json_str)

        tasks = [Task(**task_dict) for task_dict in data.get("tasks", [])]

        return cls(
            schema_version=data.get("schema_version", 1),
            state=data.get("state", TASK_LIST_STATE_CREATED),
            tasks=tasks,
        )