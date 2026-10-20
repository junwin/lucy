"""Shared FCP correlation setup and metrics finalization.

Presentation paths retain ownership of when setup/finalization is called. This
module does not yield SSE events or change generator cleanup semantics.
"""
import contextvars
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, NamedTuple, Optional

from src.message_processors.fcp_models import ProcessorContext
from src.message_processors.run_metrics import RunMetrics
from src.metrics import CorrelationLogHandler, RunMetricsLogger


_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "fcp_correlation_id", default="-"
)


class _CorrelationIdFilter(logging.Filter):
    """Inject the active FCP correlation id into log records.

    Same pattern as RequestIdFilter in app.py: a filter attached to the
    correlation handler stamps a contextvar-backed id onto every record so
    the handler can attribute ERROR/WARNING counts to the active run.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_var.get("-")
        return True


_CORRELATION_HANDLER = CorrelationLogHandler()
_CORRELATION_HANDLER.addFilter(_CorrelationIdFilter())


def _utc_now_iso() -> str:
    """Return the current UTC time as ISO-8601 with milliseconds and a Z suffix."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _resolve_metrics_logger(config: Any) -> Optional[RunMetricsLogger]:
    """Resolve the runs log logger from config, or None when unconfigured.

    Priority: explicit ``metrics_runs_log_path``, then the design default
    ``<storage_root_path>/<storage_namespace>/metrics/runs.jsonl``.
    """

    if config is None:
        return None
    path = config.get("metrics_runs_log_path")
    if not path:
        storage_root = config.get("storage_root_path")
        if storage_root:
            path = os.path.join(
                str(storage_root),
                str(config.get("storage_namespace") or ""),
                "metrics",
                "runs.jsonl",
            )
    if not path:
        return None
    return RunMetricsLogger(path)


def _build_run_metrics(
    metrics: Dict[str, Any],
    ctx: Optional[ProcessorContext],
    correlation_id: str,
    latency_ms: int,
    started: str = "",
    errors: int = 0,
    warnings: int = 0,
) -> RunMetrics:
    failures = metrics.get("failures", 0)
    hit_iteration_cap = metrics.get("hit_iteration_cap", False)
    return RunMetrics(
        correlation_id=correlation_id,
        iterations=metrics.get("iterations", 0),
        max_iterations=ctx.max_iterations if ctx is not None else 0,
        hit_iteration_cap=hit_iteration_cap,
        openai_calls=metrics.get("openai_calls", 0),
        tool_calls=metrics.get("tool_calls", 0),
        prompt_tokens=metrics.get("prompt_tokens", 0),
        completion_tokens=metrics.get("completion_tokens", 0),
        total_tokens=metrics.get("total_tokens", 0),
        failures=failures,
        tool_failures=metrics.get("tool_failures", 0),
        processor_failures=metrics.get("processor_failures", 0),
        tool_error=metrics.get("tool_error"),
        duration_ms=latency_ms,
        agent=ctx.agent_name if ctx is not None else "",
        account=ctx.account_id if ctx is not None else "",
        session_id=ctx.conversation_id if ctx is not None else "",
        started=started,
        errors=errors,
        warnings=warnings,
        success=not (hit_iteration_cap or failures > 0),
    )


class RunStart(NamedTuple):
    start_ts: float
    metrics: Dict[str, Any]
    correlation_id: str
    started: str
    correlation_token: contextvars.Token


def begin_run(
    correlation_handler: CorrelationLogHandler,
    correlation_id: Optional[str],
    *,
    now: Callable[[], str],
) -> RunStart:
    """Initialize fresh counters and activate the run's correlation identity."""
    start_ts = time.perf_counter()
    metrics: Dict[str, Any] = {
        "iterations": 0,
        "openai_calls": 0,
        "tool_calls": 0,
        "failures": 0,
        "tool_failures": 0,
        "processor_failures": 0,
        "hit_iteration_cap": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    started = now()
    correlation_handler.start_run(correlation_id)
    correlation_token = _correlation_id_var.set(correlation_id)
    return RunStart(start_ts, metrics, correlation_id, started, correlation_token)


def finalize_run(
    metrics: Dict[str, Any],
    ctx: Optional[ProcessorContext],
    correlation_id: str,
    started: str,
    latency_ms: int,
    correlation_token: Optional[contextvars.Token] = None,
    *,
    correlation_handler: CorrelationLogHandler,
    metrics_logger: Optional[RunMetricsLogger],
) -> RunMetrics:
    """End correlation-scoped counting and persist the run metrics record.

    Deregisters the run's ERROR/WARNING accumulator, reads the final
    counts, builds the RunMetrics record with the envelope fields, and
    appends it to the runs log when a logger is configured. Appending is
    best-effort: a log write failure never fails the request.
    """

    context = correlation_handler.end_run(correlation_id)
    if correlation_token is not None:
        _correlation_id_var.reset(correlation_token)
    errors = context.errors if context is not None else 0
    warnings = context.warnings if context is not None else 0
    record = _build_run_metrics(
        metrics,
        ctx,
        correlation_id,
        latency_ms,
        started=started,
        errors=errors,
        warnings=warnings,
    )
    if metrics_logger is not None:
        try:
            metrics_logger.append(record)
        except Exception:
            logging.exception(
                "FunctionCallingProcessor: failed to append run metrics record correlation_id=%s",
                correlation_id,
            )
    return record
