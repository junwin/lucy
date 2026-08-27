"""CorrelationLogHandler tests: ERROR/WARNING-only counting, active-context
matching, and reset per correlation id lifecycle (issue #131, design doc
metrics-report.md)."""

import logging

from src.message_processors.fcp_models import RequestContext
from src.metrics import CorrelationLogHandler


def _make_record(level: int, correlation_id: str = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )
    if correlation_id is not None:
        record.correlation_id = correlation_id
    return record


def test_only_error_and_warning_records_are_counted():
    handler = CorrelationLogHandler()
    handler.start_run("corr-1")

    handler.handle(_make_record(logging.DEBUG, "corr-1"))
    handler.handle(_make_record(logging.INFO, "corr-1"))
    handler.handle(_make_record(logging.CRITICAL, "corr-1"))
    handler.handle(_make_record(logging.WARNING, "corr-1"))
    handler.handle(_make_record(logging.WARNING, "corr-1"))
    handler.handle(_make_record(logging.ERROR, "corr-1"))
    handler.handle(_make_record(logging.ERROR, "corr-1"))

    context = handler.end_run("corr-1")
    assert context is not None
    assert context.errors == 2
    assert context.warnings == 2


def test_records_without_matching_active_context_are_ignored():
    handler = CorrelationLogHandler()
    handler.start_run("corr-1")

    handler.handle(_make_record(logging.ERROR))
    handler.handle(_make_record(logging.WARNING, "corr-unknown"))
    handler.handle(_make_record(logging.ERROR, ""))

    context = handler.end_run("corr-1")
    assert context is not None
    assert context.errors == 0
    assert context.warnings == 0


def test_counts_reset_per_correlation_id_lifecycle():
    handler = CorrelationLogHandler()

    first = handler.start_run("corr-1")
    handler.handle(_make_record(logging.ERROR, "corr-1"))
    handler.handle(_make_record(logging.WARNING, "corr-1"))
    assert first.errors == 1
    assert first.warnings == 1

    finished = handler.end_run("corr-1")
    assert finished is first
    assert finished.errors == 1
    assert finished.warnings == 1
    assert handler.end_run("corr-1") is None

    second = handler.start_run("corr-1")
    assert second.errors == 0
    assert second.warnings == 0
    handler.handle(_make_record(logging.ERROR, "corr-1"))
    assert second.errors == 1

    finished_again = handler.end_run("corr-1")
    assert finished_again is not None
    assert finished_again.errors == 1
    assert finished_again.warnings == 0


def test_start_run_returns_accumulator_exposing_counts():
    handler = CorrelationLogHandler()
    context = handler.start_run("corr-1")

    assert isinstance(context, RequestContext)
    assert context.correlation_id == "corr-1"
    assert context.errors == 0
    assert context.warnings == 0


def test_counts_via_real_logger_with_correlation_filter():
    class CorrelationIdFilter(logging.Filter):
        def __init__(self, correlation_id: str):
            super().__init__()
            self.correlation_id = correlation_id

        def filter(self, record: logging.LogRecord) -> bool:
            record.correlation_id = self.correlation_id
            return True

    handler = CorrelationLogHandler()
    logger = logging.getLogger("test-correlation-log-handler")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)

    try:
        active = "corr-live"
        handler.start_run(active)
        logger.addFilter(CorrelationIdFilter(active))

        logger.info("not counted")
        logger.warning("counted as warning")
        logger.error("counted as error")

        context = handler.end_run(active)
        assert context is not None
        assert context.errors == 1
        assert context.warnings == 1
    finally:
        logger.removeHandler(handler)
        logger.handlers.clear()
        logger.filters.clear()
