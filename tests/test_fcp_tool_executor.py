import logging

import pytest
from unittest.mock import Mock, patch

from src.message_processors.fcp_models import ProcessorContext, ToolHandlerError, _ToolCall
from src.message_processors.fcp_tool_executor import ToolExecutor
from src.metrics.tool_call_digest import args_digest, error_signature
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


def _execute_completed_result(result, *, iteration=4):
    from tests.conftest import FakeAgent, FakeConfig, FakeHandler, FakeRegistry

    handler = FakeHandler(result)
    registry = FakeRegistry(
        handler_by_name={"sample_tool": handler},
        tool_defs=[{"name": "sample_tool"}],
    )
    trace_logger = Mock(spec=ToolCallTraceLogger)
    llm_adapter = Mock()
    llm_adapter.format_tool_output.return_value = {"type": "function_call_output"}
    prompt_builder = Mock()
    prompt_builder._get_context_state.return_value = None
    executor = ToolExecutor(
        registry=registry,
        config=FakeConfig(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
        agent_manager=None,
        trace_logger=trace_logger,
    )
    agent = FakeAgent()
    ctx = ProcessorContext.from_agent(
        primary_agent=agent,
        account={"accountId": "acct1"},
        conversation_id="conversation-1",
        context_name="context-1",
    )
    metrics = {"tool_calls": 0}
    call = _ToolCall(
        name="sample_tool",
        call_id="call-1",
        arguments_raw='{"b":2,"a":1}',
    )

    executor.execute_tool_calls(
        tool_calls=[call],
        primary_agent=agent,
        secondary_agent=None,
        processor_factory=None,
        account={"accountId": "acct1"},
        ctx=ctx,
        metrics=metrics,
        correlation_id="correlation-1",
        parent_correlation_id="parent-1",
        iteration=iteration,
    )

    trace_logger.append.assert_called_once()
    return trace_logger.append.call_args.args[0], metrics


def test_execute_tool_calls_traces_success_result():
    trace, metrics = _execute_completed_result({"ok": True, "value": 42})

    assert trace.correlation_id == "correlation-1"
    assert trace.parent_correlation_id == "parent-1"
    assert trace.iteration == 4
    assert trace.tool_name == "sample_tool"
    assert trace.call_id == "call-1"
    assert trace.args_digest == args_digest('{"b":2,"a":1}')
    assert trace.ok is True
    assert trace.error_code is None
    assert trace.error_signature is None
    assert trace.duration_ms >= 0
    assert trace.ts.endswith("Z")
    assert metrics == {"tool_calls": 1}


def test_execute_tool_calls_traces_ok_false_result():
    result = {"ok": False, "error": "Validation failed."}
    trace, metrics = _execute_completed_result(result, iteration=7)
    assert trace.correlation_id == "correlation-1"
    assert trace.parent_correlation_id == "parent-1"
    assert trace.iteration == 7
    assert trace.ok is False
    assert trace.error_code == "other"
    assert trace.error_signature == error_signature("Validation failed.")
    assert trace.duration_ms >= 0
    assert trace.ts.endswith("Z")
    assert metrics == {"tool_calls": 1, "tool_failures": 1, "failures": 1}


def _executor_context(agent):
    return ProcessorContext.from_agent(
        primary_agent=agent,
        account={"accountId": "acct1"},
        conversation_id="conversation-1",
        context_name="context-1",
    )


def test_execute_tool_calls_traces_unknown_tool():
    from tests.conftest import FakeAgent, FakeConfig, FakeRegistry

    trace_logger = Mock(spec=ToolCallTraceLogger)
    llm_adapter = Mock()
    llm_adapter.format_tool_output.return_value = {"type": "function_call_output"}
    prompt_builder = Mock()
    prompt_builder._get_context_state.return_value = None
    executor = ToolExecutor(
        registry=FakeRegistry(),
        config=FakeConfig(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
        agent_manager=None,
        trace_logger=trace_logger,
    )
    agent = FakeAgent()
    metrics = {"tool_calls": 0}

    executor.execute_tool_calls(
        tool_calls=[
            _ToolCall(
                name="missing_tool",
                call_id="call-unknown",
                arguments_raw='{"query":"secret"}',
            )
        ],
        primary_agent=agent,
        secondary_agent=None,
        processor_factory=None,
        account={"accountId": "acct1"},
        ctx=_executor_context(agent),
        metrics=metrics,
        correlation_id="correlation-unknown",
        parent_correlation_id="parent-1",
        iteration=2,
    )

    trace_logger.append.assert_called_once()
    trace = trace_logger.append.call_args.args[0]
    assert trace.correlation_id == "correlation-unknown"
    assert trace.parent_correlation_id == "parent-1"
    assert trace.iteration == 2
    assert trace.tool_name == "missing_tool"
    assert trace.call_id == "call-unknown"
    assert trace.args_digest == args_digest('{"query":"secret"}')
    assert trace.ok is False
    assert trace.error_code == "unknown_tool"
    assert trace.error_signature == error_signature(
        "Unknown tool 'missing_tool'. Valid tools: []"
    )
    assert metrics == {"tool_calls": 1, "tool_failures": 1, "failures": 1}


def test_execute_tool_calls_traces_too_large_result():
    from tests.conftest import FakeAgent, FakeConfig, FakeHandler, FakeRegistry

    handler = FakeHandler({"ok": True, "payload": "x" * 200})
    registry = FakeRegistry(handler_by_name={"large_tool": handler})
    trace_logger = Mock(spec=ToolCallTraceLogger)
    llm_adapter = Mock()
    llm_adapter.format_tool_output.return_value = {"type": "function_call_output"}
    prompt_builder = Mock()
    prompt_builder._get_context_state.return_value = None
    executor = ToolExecutor(
        registry=registry,
        config=FakeConfig(values={"max_tool_result_chars": 40}),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
        agent_manager=None,
        trace_logger=trace_logger,
    )
    agent = FakeAgent()
    metrics = {"tool_calls": 0}

    executor.execute_tool_calls(
        tool_calls=[
            _ToolCall(
                name="large_tool",
                call_id="call-large",
                arguments_raw="{}",
            )
        ],
        primary_agent=agent,
        secondary_agent=None,
        processor_factory=None,
        account={"accountId": "acct1"},
        ctx=_executor_context(agent),
        metrics=metrics,
        correlation_id="correlation-large",
        parent_correlation_id=None,
        iteration=3,
    )

    trace_logger.append.assert_called_once()
    trace = trace_logger.append.call_args.args[0]
    assert trace.correlation_id == "correlation-large"
    assert trace.parent_correlation_id is None
    assert trace.iteration == 3
    assert trace.tool_name == "large_tool"
    assert trace.call_id == "call-large"
    assert trace.ok is False
    assert trace.error_code == "result_too_large"
    assert trace.error_signature is not None
    assert trace.duration_ms >= 0
    assert trace.ts.endswith("Z")
    assert metrics == {"tool_calls": 1, "tool_failures": 1, "failures": 1}


def test_execute_tool_calls_traces_missing_call_id_before_raising():
    from tests.conftest import FakeAgent, FakeConfig, FakeRegistry

    trace_logger = Mock(spec=ToolCallTraceLogger)
    prompt_builder = Mock()
    prompt_builder._get_context_state.return_value = None
    executor = ToolExecutor(
        registry=FakeRegistry(),
        config=FakeConfig(),
        prompt_builder=prompt_builder,
        llm_adapter=Mock(),
        agent_manager=None,
        trace_logger=trace_logger,
    )
    agent = FakeAgent()
    metrics = {"tool_calls": 0}

    with pytest.raises(ToolHandlerError, match="Tool call missing id/call_id"):
        executor.execute_tool_calls(
            tool_calls=[
                _ToolCall(
                    name="sample_tool",
                    call_id="",
                    arguments_raw='{"value":1}',
                )
            ],
            primary_agent=agent,
            secondary_agent=None,
            processor_factory=None,
            account={"accountId": "acct1"},
            ctx=_executor_context(agent),
            metrics=metrics,
            correlation_id="correlation-missing-id",
            parent_correlation_id="parent-1",
            iteration=5,
        )

    trace_logger.append.assert_called_once()
    trace = trace_logger.append.call_args.args[0]
    assert trace.correlation_id == "correlation-missing-id"
    assert trace.parent_correlation_id == "parent-1"
    assert trace.iteration == 5
    assert trace.tool_name == "sample_tool"
    assert trace.call_id == ""
    assert trace.args_digest == args_digest('{"value":1}')
    assert trace.ok is False
    assert trace.error_code == "tool_handler_error"
    assert trace.error_signature == error_signature(
        "ToolHandlerError: Tool call missing id/call_id for tool "
        "'sample_tool'. Cannot send function_call_output."
    )
    assert metrics == {"tool_calls": 1, "tool_failures": 1, "failures": 1}


def test_execute_tool_calls_traces_handler_exception_before_raising():
    from tests.conftest import FakeAgent, FakeConfig, FakeHandler, FakeRegistry

    handler = FakeHandler(exc=RuntimeError("boom"))
    registry = FakeRegistry(handler_by_name={"sample_tool": handler})
    trace_logger = Mock(spec=ToolCallTraceLogger)
    prompt_builder = Mock()
    prompt_builder._get_context_state.return_value = None
    executor = ToolExecutor(
        registry=registry,
        config=FakeConfig(),
        prompt_builder=prompt_builder,
        llm_adapter=Mock(),
        agent_manager=None,
        trace_logger=trace_logger,
    )
    agent = FakeAgent()
    metrics = {"tool_calls": 0}

    with pytest.raises(ToolHandlerError, match="RuntimeError: boom"):
        executor.execute_tool_calls(
            tool_calls=[
                _ToolCall(
                    name="sample_tool",
                    call_id="call-error",
                    arguments_raw='{"value":1}',
                )
            ],
            primary_agent=agent,
            secondary_agent=None,
            processor_factory=None,
            account={"accountId": "acct1"},
            ctx=_executor_context(agent),
            metrics=metrics,
            correlation_id="correlation-error",
            parent_correlation_id=None,
            iteration=6,
        )

    trace_logger.append.assert_called_once()
    trace = trace_logger.append.call_args.args[0]
    assert trace.correlation_id == "correlation-error"
    assert trace.parent_correlation_id is None
    assert trace.iteration == 6
    assert trace.tool_name == "sample_tool"
    assert trace.call_id == "call-error"
    assert trace.args_digest == args_digest('{"value":1}')
    assert trace.ok is False
    assert trace.error_code == "tool_handler_error"
    assert trace.error_signature == error_signature("RuntimeError: boom")
    assert trace.duration_ms >= 0
    assert trace.ts.endswith("Z")
    assert metrics == {"tool_calls": 1, "tool_failures": 1, "failures": 1}
