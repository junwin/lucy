from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    # Pydantic is optional in some environments; when available we use its
    # TypeAdapter boundary for strict validation (extra fields forbidden).
    from pydantic import BaseModel, TypeAdapter, ConfigDict, ValidationError  # type: ignore
    _HAS_PYDANTIC = True
except Exception:
    _HAS_PYDANTIC = False

from .task_states import TASK_STATE_PENDING


@dataclass(init=False)
class Task:
    """Domain Task dataclass.

    Notes:
    - Domain object remains a lightweight dataclass.
    - Validation and boundary checks are performed via a Pydantic
      model/TypeAdapter at the edges (from_dict/from_json) when available.
    """

    id: str
    instructions: str
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: Any,
        instructions: Optional[str] = None,
        *,
        title: Optional[str] = None,
        state: str = TASK_STATE_PENDING,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Prefer explicit instructions, fall back to legacy title
        if instructions is None and title is not None:
            instructions = title

        if instructions is None:
            raise TypeError("Task requires 'instructions' (or legacy 'title')")

        # Normalize id: accept ints (legacy) by creating deterministic UUID
        if isinstance(id, int):
            id = str(uuid.uuid5(uuid.NAMESPACE_OID, str(id)))
        else:
            id = str(id)

        self.id = id
        self.instructions = instructions
        self.state = state or TASK_STATE_PENDING
        self.result = result
        self.error = error
        self.meta = meta or {}

    @property
    def title(self) -> str:
        return self.instructions

    @title.setter
    def title(self, v: str) -> None:
        self.instructions = v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "instructions": str(self.instructions),
            "state": str(self.state),
            "result": self.result if self.result is not None else None,
            "error": self.error if self.error is not None else None,
            "meta": dict(self.meta) if self.meta is not None else {},
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        allow_legacy: bool = True,
        allow_legacy_meta: bool = False,
    ) -> "Task":
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")

        payload = dict(data)
        legacy = False
        if "title" in payload or "status" in payload or isinstance(payload.get("id"), int) or "name" in payload:
            legacy = True

        if legacy and not allow_legacy:
            raise ValueError("Legacy Task shape detected; set allow_legacy=True to permit migration")

        # Map legacy keys
        if "title" in payload:
            payload.setdefault("instructions", payload.pop("title"))
        if "name" in payload:
            payload.setdefault("instructions", payload.pop("name"))
        if "status" in payload:
            payload.setdefault("state", payload.pop("status"))

        # Normalize id
        raw_id = payload.get("id")
        if isinstance(raw_id, int):
            payload["id"] = str(uuid.uuid5(uuid.NAMESPACE_OID, str(raw_id)))
        elif isinstance(raw_id, str):
            payload["id"] = raw_id

        # Allowed keys
        allowed = {"id", "instructions", "state", "result", "error", "meta"}
        extra_keys = set(payload.keys()) - allowed
        if extra_keys:
            if legacy and allow_legacy_meta:
                meta = dict(payload.get("meta") or {})
                for k in list(extra_keys):
                    meta[k] = payload.pop(k)
                payload["meta"] = meta
                extra_keys = set()
            else:
                raise ValueError(f"Unknown Task fields: {sorted(extra_keys)}")

        # If pydantic is available, use TypeAdapter with extra=forbid for strict validation
        if _HAS_PYDANTIC:
            class _TaskModel(BaseModel):
                model_config = ConfigDict(extra="forbid")

                id: str
                instructions: str
                state: str = TASK_STATE_PENDING
                result: Optional[Dict[str, Any]] = None
                error: Optional[str] = None
                meta: Dict[str, Any] = {}

            try:
                ta = TypeAdapter(_TaskModel)
                validated = ta.validate_python(payload)
            except ValidationError as exc:
                raise ValueError(f"Task validation error: {exc}") from exc

            return cls(
                id=str(validated.id),
                instructions=str(validated.instructions),
                state=str(validated.state),
                result=validated.result,
                error=validated.error,
                meta=validated.meta or {},
            )

        # Fallback validation when pydantic not available
        try:
            tid = payload["id"]
            instr = payload["instructions"]
        except KeyError as exc:
            raise ValueError(f"Missing required Task field: {exc}") from exc

        if not isinstance(instr, str):
            raise ValueError("Task.instructions must be a string")

        state = payload.get("state", TASK_STATE_PENDING) or TASK_STATE_PENDING
        if not isinstance(state, str):
            raise ValueError("Task.state must be a string")

        result = payload.get("result")
        if result is not None and not isinstance(result, dict):
            raise ValueError("Task.result must be a dict or null")

        error = payload.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("Task.error must be a string or null")

        meta = payload.get("meta", {})
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ValueError("Task.meta must be a dict")

        # Normalize id: if integer-like, convert to deterministic UUID string
        if isinstance(tid, int):
            tid = str(uuid.uuid5(uuid.NAMESPACE_OID, str(tid)))
        else:
            tid = str(tid)

        return cls(id=tid, instructions=instr, state=state, result=result, error=error, meta=meta)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "Task":
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON for Task") from exc
        return cls.from_dict(data)
