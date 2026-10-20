"""Build automation execution records; persistence stays in the coordinator."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.execution_identity import ExecutionIdentity
    from src.tasklists.task import Task
    from src.tasklists.task_list import TaskList


def build_task_execution_record(
    *,
    tasklist: TaskList,
    task: Task,
    resolved_key: str,
    started_at: str,
    child_identity: Optional[ExecutionIdentity],
    task_result: Optional[dict],
    task_error: Optional[str],
    run_metrics: Optional[dict],
    error_detail: Optional[str],
    now: Callable[[], datetime],
) -> dict:
    """Retain record schema, optional-field rules and parent/child identity."""
    record: dict = {
        "schema_version": 1,
        "record_id": uuid.uuid4().hex,
        "tasklist_key": resolved_key,
        "task_id": task.id,
        "task_name": task.name,
        "state": "completed" if task_error is None else "failed",
        "started": started_at,
        "ended": now().isoformat(),
    }
    task_meta = tasklist.meta if isinstance(getattr(tasklist, "meta", None), dict) else {}
    correlation = task_meta.get("correlation_id")
    if correlation:
        record["correlation_id"] = correlation
    if child_identity is not None:
        record["trace_id"] = child_identity.trace_id
        record["run_id"] = child_identity.run_id
        record["parent_run_id"] = child_identity.parent_run_id
    if task_error is not None:
        record["error"] = task_error
        if error_detail is not None:
            record["error_detail"] = error_detail
    if run_metrics is not None:
        record["metrics"] = run_metrics
    if task_result is not None:
        record["result"] = task_result
    return record
