"""Metrics logging package (issue #131, design doc metrics-report.md).

Public API — ``RunMetricsLogger``, the append-only JSONL writer for
per-FCP-run metrics records, ``CorrelationLogHandler``, the
correlation-scoped ERROR/WARNING counter that feeds each run record,
``MetricsRepository``, the read-only query layer over the runs log, and
``ToolCallTraceLogger``, the append-only JSONL writer for per-tool-call
trace records.
"""

from .run_metrics_logger import RunMetricsLogger
from .correlation_log_handler import CorrelationLogHandler
from .metrics_repository import MetricsRepository
from .tool_call_trace_logger import ToolCallTraceLogger

__all__ = [
    "RunMetricsLogger",
    "CorrelationLogHandler",
    "MetricsRepository",
    "ToolCallTraceLogger",
]
