from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional, Protocol, runtime_checkable


# -----------------------------
# Vocabulary (shared constants)
# -----------------------------

# Task list states
TASK_LIST_STATE_CREATED = "Created"
TASK_LIST_STATE_RUNNING = "Running"
TASK_LIST_STATE_COMPLETED = "Completed"
TASK_LIST_STATE_FAILED = "Failed"

# Task states
TASK_STATE_PENDING = "Pending"
TASK_STATE_RUNNING = "Running"
TASK_STATE_COMPLETED = "Completed"
TASK_STATE_COMPLETED_WITH_ERRORS = "Completed (with errors)"
TASK_STATE_FAILED = "Failed"
TASK_STATE_BLOCKED = "Blocked"


# -----------------------------
# Task interface
# -----------------------------

@runtime_checkable
class AbstractTask(Protocol):
    """Interface for a single task/step in a task list.

    Concrete implementations may store data in memory, files, nodes, etc.,
    but must expose at least these attributes and behaviours.
    """

    # Required attributes
    task_id: str
    description: str
    state: str
    result: Optional[str]

    def to_dict(self) -> dict:
        """Return a serialisable representation of this task."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "AbstractTask":
        """Create a task instance from a serialised representation."""
        ...


# -----------------------------
# Task list interface
# -----------------------------


class AbstractTaskList(ABC):
    """Abstract base class for a task list.

    A task list is a shallow list of tasks that can be serialised as a single
    string and persisted (e.g. to disk, or into a node's info field).
    """

    # Concrete implementations must define these attributes
    task_list_id: str
    state: str

    # ---- metadata ----

    @property
    @abstractmethod
    def title(self) -> str:
        """Human-facing title for this task list."""
        raise NotImplementedError

    @title.setter
    @abstractmethod
    def title(self, value: str) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-facing description for this task list."""
        raise NotImplementedError

    @description.setter
    @abstractmethod
    def description(self, value: str) -> None:
        raise NotImplementedError

    # ---- task access ----

    @abstractmethod
    def tasks(self) -> Iterable[AbstractTask]:
        """Return an iterable of tasks in this list, in execution order."""
        raise NotImplementedError

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[AbstractTask]:
        """Return the task with the given id, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def add_task(self, task: AbstractTask) -> None:
        """Add a task to this list.

        If a task with the same task_id already exists, it should be replaced
        (keeping the overall order where possible).
        """
        raise NotImplementedError

    @abstractmethod
    def update_task_state(self, task_id: str, new_state: str) -> None:
        """Update the state of the task with the given id, if it exists."""
        raise NotImplementedError

    @abstractmethod
    def set_task_result(
        self,
        task_id: str,
        result: str,
        *,
        new_state: Optional[str] = None,
    ) -> None:
        """Set the result string for a task, and optionally update its state.

        If new_state is provided, the task's state should be set to that value.
        """
        raise NotImplementedError

    # ---- serialisation ----

    @abstractmethod
    def to_dict(self) -> dict:
        """Convert this task list (and its tasks) to a plain dict suitable
        for JSON serialisation.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "AbstractTaskList":
        """Create a task list from a dict (inverse of to_dict)."""
        raise NotImplementedError

    @abstractmethod
    def to_json(self, *, indent: Optional[int] = None) -> str:
        """Serialise this task list to a JSON string.

        The result must be suitable for storing in a single string field
        or persisting to disk.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_json(cls, s: str) -> "AbstractTaskList":
        """Parse a task list from a JSON string produced by to_json()."""
        raise NotImplementedError
