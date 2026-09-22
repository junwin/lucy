import logging
from unittest.mock import Mock, patch

from src.message_processors.fcp_tool_executor import ToolExecutor
from src.metrics.tool_call_trace import ToolCallTrace
from src.metrics.tool_call_trace_logger import ToolCallTraceLogger


def _make_executor(trace_logger):
    return ToolExecutor(
        registry=Mock(),
        config=Mock(),
        prompt_builder=Mock(),
        llm_adapter=Mock(),
        agent_manager=None,
        trace_logger=trace_logger,
    )


def test_trace_append_failure_is_swallowed(caplog):
    trace_logger = Mock(spec=ToolCallTraceLogger)
    trace_logger.append.side_effect = OSError("disk unavailable")
    executor = _make_executor(trace_logger)
    trace = ToolCallTrace(
        correlation_id="correlation-1",
        tool_name="file_load",
        call_id="call-1",
    )

    with caplog.at_level(logging.WARNING):
        executor._append_trace(trace)

    trace_logger.append.assert_called_once_with(trace)
    assert "Tool call trace append failed" in caplog.text
    assert "correlation-1" in caplog.text


def test_trace_append_is_skipped_when_logger_is_none():
    executor = _make_executor(None)
    trace = ToolCallTrace(
        correlation_id="correlation-1",
        tool_name="file_load",
        call_id="call-1",
    )

    with patch.object(ToolCallTraceLogger, "append") as append:
        executor._append_trace(trace)

    append.assert_not_called()
