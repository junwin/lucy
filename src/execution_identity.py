"""Server-owned identifiers for one execution and its trace lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionIdentity:
    trace_id: str
    run_id: str
    parent_run_id: Optional[str] = None
    message_id: Optional[str] = None

    @classmethod
    def root(cls, *, message_id: Optional[str] = None) -> "ExecutionIdentity":
        run_id = str(uuid4())
        return cls(
            trace_id=run_id,
            run_id=run_id,
            message_id=message_id,
        )

    def child(self) -> "ExecutionIdentity":
        return type(self)(
            trace_id=self.trace_id,
            run_id=str(uuid4()),
            parent_run_id=self.run_id,
            message_id=self.message_id,
        )
