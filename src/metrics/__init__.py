"""Metrics logging package (issue #131, design doc metrics-report.md).

Public API — ``RunMetricsLogger``, the append-only JSONL writer for
per-FCP-run metrics records, ``CorrelationLogHandler``, the
correlation-scoped ERROR/WARNING counter that feeds each run record, and
``MetricsRepository``, the read-only query layer over the runs log.
"""

from .run_metrics_logger import RunMetricsLogger
from .correlation_log_handler import CorrelationLogHandler
from .metrics_repository import MetricsRepository

__all__ = [
    "RunMetricsLogger",
    "CorrelationLogHandler",
    "MetricsRepository",
]
