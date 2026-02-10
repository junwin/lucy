# src/tasklists/__init__.py
"""
Compatibility layer for Tasklist V2.

This module exposes both the legacy domain classes (Task, TaskList)
and new Pydantic-backed models (TaskModel, TaskListModel) and a
small TaskListManager that implements PUT as patch+upsert logic.

We keep the legacy classes available for backward compatibility by
importing them from the legacy modules. The Pydantic models are thin
wrappers that interoperate with the legacy classes where convenient.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    # Prefer the existing implementations if present (legacy dataclasses)
    from .task import Task as LegacyTask
    from .task_list import TaskList as LegacyTaskList
except Exception:
    LegacyTask = None  # type: ignore
    LegacyTaskList = None  # type: ignore

# Expose legacy names by default for compatibility
Task = LegacyTask
TaskList = LegacyTaskList

# Provide Pydantic models as the V2 surface. They are thin adapters
# around the legacy classes to avoid changing the rest of the codebase
# in this single-file migration step.
try:
    from pydantic import BaseModel, Field

    class TaskModel(BaseModel):
        id: str
        title: str
        instructions: str
        state: Optional[str] = None
        result: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        meta: Dict[str, Any] = Field(default_factory=dict)

        def to_legacy(self) -> Optional[LegacyTask]:
            if LegacyTask is None:
                return None
            return LegacyTask(
                id=self.id,
                title=self.title,
                instructions=self.instructions,
                state=self.state or None,
                result=self.result,
                error=self.error,
                meta=self.meta,
            )

        @classmethod
        def from_legacy(cls, t: Any) -> "TaskModel":
            return cls(
                id=str(t.id),
                title=getattr(t, "title", getattr(t, "_title", "")),
                instructions=t.instructions,
                state=getattr(t, "state", None),
                result=getattr(t, "result", None),
                error=getattr(t, "error", None),
                meta=getattr(t, "meta", {}) or {},
            )

    class TaskListModel(BaseModel):
        schema_version: int = 2
        id: str
        state: Optional[str] = None
        tasks: List[TaskModel] = Field(default_factory=list)
        meta: Dict[str, Any] = Field(default_factory=dict)
        current_task_id: Optional[str] = None
        name: Optional[str] = None

        def to_legacy(self) -> Optional[LegacyTaskList]:
            if LegacyTaskList is None:
                return None
            tasks = [t.to_legacy() for t in self.tasks]
            # filter out None if legacy not available
            tasks = [t for t in tasks if t is not None]
            return LegacyTaskList(
                id=self.id,
                schema_version=self.schema_version,
                state=self.state or (getattr(LegacyTaskList, "state", None) or None),
                tasks=tasks,
                meta=self.meta,
                current_task_id=self.current_task_id,
                name=self.name,
            )

        @classmethod
        def from_legacy(cls, tl: Any) -> "TaskListModel":
            tasks = []
            for t in getattr(tl, "tasks", []) or []:
                tasks.append(TaskModel.from_legacy(t))
            return cls(
                schema_version=getattr(tl, "schema_version", 2),
                id=str(getattr(tl, "id")),
                state=getattr(tl, "state", None),
                tasks=tasks,
                meta=getattr(tl, "meta", {}) or {},
                current_task_id=getattr(tl, "current_task_id", None),
                name=getattr(tl, "name", None),
            )

except Exception:
    # If pydantic is not available, provide lightweight fallbacks
    TaskModel = None  # type: ignore
    TaskListModel = None  # type: ignore


class TaskListManager:
    """A tiny in-memory manager implementing PUT as patch+upsert.

    Behavior:
    - put(existing: Optional[TaskListModel|LegacyTaskList], patch: Dict) -> TaskListModel
      * If existing is None, create a new TaskListModel from patch (upsert)
      * If existing is present, apply patch fields and only normalize/validate
        when performing the PUT (i.e., here). This mirrors the requirement that
        normalization happens only on PUT.
    """

    def __init__(self):
        self.store: Dict[str, Any] = {}

    def get(self, id: str) -> Optional[Any]:
        return self.store.get(id)

    def put(self, id: str, payload: Dict[str, Any]) -> Any:
        """Patch+upsert semantics: merge payload into existing object if present.

        Returns the stored TaskListModel (or legacy TaskList if pydantic not available).
        """
        existing = self.store.get(id)

        # If we have pydantic models available, use them as canonical representation
        if TaskListModel is not None:
            if existing is None:
                base = {"id": id, "schema_version": payload.get("schema_version", 2)}
            else:
                # existing may be legacy or model
                if isinstance(existing, TaskListModel):
                    base = existing.model_dump()
                else:
                    # try to convert legacy to model
                    try:
                        base = TaskListModel.from_legacy(existing).model_dump()
                    except Exception:
                        base = {"id": id, "schema_version": 2}

            # apply patch (shallow merge)
            merged = dict(base)
            merged.update(payload or {})

            # Only normalize/validate here when creating/updating (PUT)
            tl = TaskListModel.model_validate(merged)
            self.store[id] = tl
            return tl

        # Fallback to storing raw payload
        merged = dict(getattr(existing, "to_dict", lambda: {})() if existing is not None else {})
        merged.update(payload or {})
        self.store[id] = merged
        return merged


__all__ = [
    "Task",
    "TaskList",
    "TaskModel",
    "TaskListModel",
    "TaskListManager",
]
