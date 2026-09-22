from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel


class _ToolCallTraceModel(BaseModel):
    correlation_id: str = ""
    parent_correlation_id: Optional[str] = None
    iteration: int = 0
    tool_name: str = ""
    call_id: str = ""
    args_digest: str = ""
    ok: bool = True
    error_code: Optional[str] = None
    error_signature: Optional[str] = None
    duration_ms: int = 0
    ts: str = ""

    model_config = {"extra": "forbid"}


@dataclass(init=False)
class ToolCallTrace:
    correlation_id: str = ""
    parent_correlation_id: Optional[str] = None
    iteration: int = 0
    tool_name: str = ""
    call_id: str = ""
    args_digest: str = ""
    ok: bool = True
    error_code: Optional[str] = None
    error_signature: Optional[str] = None
    duration_ms: int = 0
    ts: str = ""

    def __init__(
        self,
        correlation_id: str = "",
        parent_correlation_id: Optional[str] = None,
        iteration: int = 0,
        tool_name: str = "",
        call_id: str = "",
        args_digest: str = "",
        ok: bool = True,
        error_code: Optional[str] = None,
        error_signature: Optional[str] = None,
        duration_ms: int = 0,
        ts: str = "",
    ) -> None:
        self.correlation_id = correlation_id
        self.parent_correlation_id = parent_correlation_id
        self.iteration = iteration
        self.tool_name = tool_name
        self.call_id = call_id
        self.args_digest = args_digest
        self.ok = ok
        self.error_code = error_code
        self.error_signature = error_signature
        self.duration_ms = duration_ms
        self.ts = ts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "parent_correlation_id": self.parent_correlation_id,
            "iteration": self.iteration,
            "tool_name": self.tool_name,
            "call_id": self.call_id,
            "args_digest": self.args_digest,
            "ok": self.ok,
            "error_code": self.error_code,
            "error_signature": self.error_signature,
            "duration_ms": self.duration_ms,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCallTrace":
        if not isinstance(data, dict):
            raise TypeError("ToolCallTrace.from_dict expects a dict")

        try:
            validated = _ToolCallTraceModel.model_validate(data)
        except Exception as exc:
            raise ValueError(f"ToolCallTrace validation error: {exc}") from exc

        return cls(
            correlation_id=validated.correlation_id,
            parent_correlation_id=validated.parent_correlation_id,
            iteration=validated.iteration,
            tool_name=validated.tool_name,
            call_id=validated.call_id,
            args_digest=validated.args_digest,
            ok=validated.ok,
            error_code=validated.error_code,
            error_signature=validated.error_signature,
            duration_ms=validated.duration_ms,
            ts=validated.ts,
        )
