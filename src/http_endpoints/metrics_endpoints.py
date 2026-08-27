"""HTTP endpoint for querying FCP run metrics (issue #131, design doc
metrics-report.md).

Provides the implementation behind the read-only ``GET /metrics/runs`` route.
Query parameters map to ``MetricsRepository`` filters; ``limit`` defaults to
50 and is clamped to 500, and invalid parameter values return
``{"error": ...}`` with HTTP 400. The repository is resolved through the DI
container (``container.get``), matching the existing endpoint pattern.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from src.metrics import MetricsRepository


def _parse_bool_param(value: Optional[str], name: str) -> Tuple[Optional[bool], Optional[str]]:
    """Parse a true/false/1/0 query value into a bool.

    Returns (parsed, None) for a recognised value, (None, None) when the
    parameter is absent or empty, and (None, error) otherwise. Matching is
    case-insensitive.
    """

    if value is None or value == "":
        return None, None
    normalized = value.strip().lower()
    if normalized in ("true", "1"):
        return True, None
    if normalized in ("false", "0"):
        return False, None
    return None, f"invalid {name} value: {value!r}"


def _parse_limit(value: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Parse the limit query value into a positive integer.

    Absent or empty values default to 50; values above 500 are clamped to
    500. Non-integer or non-positive values yield an error message.
    """

    if value is None or value == "":
        return 50, None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None, f"invalid limit: {value!r}"
    if limit <= 0:
        return None, f"invalid limit: {value!r}"
    return min(limit, 500), None


def _resolve_runs_log_path(config: Any) -> str:
    """Resolve the runs log path from config.

    Priority: explicit ``metrics_runs_log_path``, then the design default
    ``<storage_root_path>/<storage_namespace>/metrics/runs.jsonl``.
    """

    if config is None:
        return "metrics/runs.jsonl"
    path = config.get("metrics_runs_log_path")
    if path:
        return path
    storage_root = config.get("storage_root_path")
    if storage_root:
        return os.path.join(
            str(storage_root),
            str(config.get("storage_namespace") or ""),
            "metrics",
            "runs.jsonl",
        )
    return "metrics/runs.jsonl"


def _resolve_repository(container: Any, config: Any) -> MetricsRepository:
    """Resolve MetricsRepository from the DI container.

    Falls back to constructing one from config when the container does not
    provide the repository (same pattern as the prompt_builder endpoints).
    """

    try:
        return container.get(MetricsRepository)
    except Exception:
        return MetricsRepository(_resolve_runs_log_path(config))


def get_metrics_runs_impl(
    container: Any,
    config: Any,
    query_params: Dict[str, Any],
) -> Tuple[Any, int]:
    """Query the runs log and return matching records, newest first.

    Supported params: correlation_id, agent, account, started, ended,
    hit_iteration_cap, success, limit. Returns 200 with
    ``{"count": n, "runs": [...]}`` or 400 with ``{"error": ...}`` for
    invalid parameter values.
    """

    limit, limit_error = _parse_limit(query_params.get("limit"))
    if limit_error is not None:
        return {"error": limit_error}, 400

    success, success_error = _parse_bool_param(query_params.get("success"), "success")
    if success_error is not None:
        return {"error": success_error}, 400

    hit_iteration_cap, cap_error = _parse_bool_param(
        query_params.get("hit_iteration_cap"), "hit_iteration_cap"
    )
    if cap_error is not None:
        return {"error": cap_error}, 400

    repository = _resolve_repository(container, config)

    try:
        runs = repository.query(
            correlation_id=query_params.get("correlation_id") or None,
            agent=query_params.get("agent") or None,
            account=query_params.get("account") or None,
            started=query_params.get("started") or None,
            ended=query_params.get("ended") or None,
            hit_iteration_cap=hit_iteration_cap,
            success=success,
            limit=limit,
        )
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:
        logging.exception("Error in /metrics/runs")
        return {"error": str(exc)}, 500

    return {"count": len(runs), "runs": runs}, 200
