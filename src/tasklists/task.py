from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .task_states import TASK_STATE_PENDING


@dataclass
class Task:
    """A single task/step in a task list.

    Domain object only:
    - No Pydantic
    - No persistence/serialization (originally)

    We add simple, explicit serialization helpers here so surrounding
    layers (storage adapters, HTTP handlers, tests) can convert domain
    objects to/from plain JSON-friendly dicts without coupling to the
    persistence implementation.
    """

    id: int
    title: str
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict representation of the Task.

        The representation is intentionally simple and stable so storage
        layers and HTTP handlers can rely on the shape.
        """
        return {
            "id": int(self.id),
            "title": str(self.title),
            "state": str(self.state),
            "result": self.result if self.result is not None else None,
            "error": self.error if self.error is not None else None,
            "meta": dict(self.meta) if self.meta is not None else {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Construct a Task from a dict produced by to_dict or from external input.

        Performs minimal validation and type coercion while keeping the
        object lightweight. Raises TypeError or ValueError on invalid input.
        """
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")

        try:
            tid = data["id"]
            title = data["title"]
        except KeyError as exc:
            raise ValueError(f"Missing required Task field: {exc}") from exc

        # Coerce and validate basic types
        try:
            tid = int(tid)
        except Exception as exc:
            # Allow string-like ids that contain digits (e.g. 't0') by extracting digits.
            if isinstance(tid, str):
                digits = "".join(ch for ch in tid if ch.isdigit())
                if digits:
                    try:
                        tid = int(digits)
                    except Exception:
                        raise ValueError("Task.id must be an integer") from exc
                else:
                    raise ValueError("Task.id must be an integer") from exc
            else:
                raise ValueError("Task.id must be an integer") from exc

        if not isinstance(title, str):
            raise ValueError("Task.title must be a string")

        state = data.get("state", TASK_STATE_PENDING)
        if state is None:
            state = TASK_STATE_PENDING
        if not isinstance(state, str):
            raise ValueError("Task.state must be a string")

        result = data.get("result")
        if result is not None and not isinstance(result, dict):
            raise ValueError("Task.result must be a dict or null")

        error = data.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("Task.error must be a string or null")

        meta = data.get("meta", {})
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ValueError("Task.meta must be a dict")

        return cls(id=tid, title=title, state=state, result=result, error=error, meta=meta)

    def to_json(self) -> str:
        """Return a compact JSON string for the task.

        Uses the to_dict representation.
        """
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "Task":
        """Construct a Task from a JSON string.

        Raises ValueError if the JSON is invalid or required fields missing.
        """
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON for Task") from exc
        return cls.from_dict(data)
