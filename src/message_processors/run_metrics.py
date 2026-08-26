from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel


class _RunMetricsModel(BaseModel):
    correlation_id: str = ""
    iterations: int = 0
    max_iterations: int = 0
    hit_iteration_cap: bool = False
    openai_calls: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    failures: int = 0
    duration_ms: int = 0

    model_config = {"extra": "forbid"}


@dataclass(init=False)
class RunMetrics:
    correlation_id: str = ""
    iterations: int = 0
    max_iterations: int = 0
    hit_iteration_cap: bool = False
    openai_calls: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    failures: int = 0
    duration_ms: int = 0

    def __init__(
        self,
        correlation_id: str = "",
        iterations: int = 0,
        max_iterations: int = 0,
        hit_iteration_cap: bool = False,
        openai_calls: int = 0,
        tool_calls: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
        failures: int = 0,
        duration_ms: int = 0,
    ) -> None:
        self.correlation_id = correlation_id
        self.iterations = iterations
        self.max_iterations = max_iterations
        self.hit_iteration_cap = hit_iteration_cap
        self.openai_calls = openai_calls
        self.tool_calls = tool_calls
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = (
            prompt_tokens + completion_tokens
            if total_tokens is None
            else total_tokens
        )
        self.failures = failures
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "hit_iteration_cap": self.hit_iteration_cap,
            "openai_calls": self.openai_calls,
            "tool_calls": self.tool_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "failures": self.failures,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunMetrics":
        if not isinstance(data, dict):
            raise TypeError("RunMetrics.from_dict expects a dict")

        try:
            validated = _RunMetricsModel.model_validate(data)
        except Exception as exc:
            raise ValueError(f"RunMetrics validation error: {exc}") from exc

        return cls(
            correlation_id=validated.correlation_id,
            iterations=validated.iterations,
            max_iterations=validated.max_iterations,
            hit_iteration_cap=validated.hit_iteration_cap,
            openai_calls=validated.openai_calls,
            tool_calls=validated.tool_calls,
            prompt_tokens=validated.prompt_tokens,
            completion_tokens=validated.completion_tokens,
            total_tokens=validated.prompt_tokens + validated.completion_tokens,
            failures=validated.failures,
            duration_ms=validated.duration_ms,
        )
