"""Correlation-scoped ERROR/WARNING counting for the run metrics log.

The handler pairs with the ``RequestContext`` accumulator in
``src/message_processors/fcp_models.py``: each FCP run registers a fresh
accumulator via ``start_run()``, log records produced during the run are
counted against it, and ``end_run()`` returns the final counts for inclusion
in the run record.
"""

import logging
import threading
from typing import Dict, Optional

from src.message_processors.fcp_models import RequestContext


class CorrelationLogHandler(logging.Handler):
    """Count ERROR/WARNING log records per active correlation id.

    A record is counted only while a matching correlation id is active, i.e.
    between ``start_run(correlation_id)`` and ``end_run(correlation_id)``.
    Records at WARNING level increment ``warnings``; records at ERROR level
    increment ``errors``; all other levels are ignored.

    Records are expected to carry a ``correlation_id`` attribute, injected by
    a logging Filter following the same pattern as ``RequestIdFilter`` in
    app.py (which stamps every record with the active ``request_id``). That
    filter lives in app.py and is not importable from ``src``; this handler
    only reads the attribute when present, so records without it are ignored.

    Counts reset per lifecycle: every ``start_run`` registers a fresh zeroed
    accumulator for the correlation id, and ``end_run`` removes it.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self._contexts: Dict[str, RequestContext] = {}
        self._lock = threading.Lock()

    def start_run(self, correlation_id: str) -> RequestContext:
        """Register a fresh accumulator for the correlation id and return it."""

        context = RequestContext(correlation_id=correlation_id)
        with self._lock:
            self._contexts[correlation_id] = context
        return context

    def end_run(self, correlation_id: str) -> Optional[RequestContext]:
        """Deregister the accumulator and return it, or None when inactive."""

        with self._lock:
            return self._contexts.pop(correlation_id, None)

    def emit(self, record: logging.LogRecord) -> None:
        """Count the record against the active context for its correlation id."""

        if record.levelno == logging.WARNING:
            field = "warnings"
        elif record.levelno == logging.ERROR:
            field = "errors"
        else:
            return

        correlation_id = getattr(record, "correlation_id", None)
        if not correlation_id:
            return

        with self._lock:
            context = self._contexts.get(correlation_id)
            if context is None:
                return
            if field == "warnings":
                context.warnings += 1
            else:
                context.errors += 1
