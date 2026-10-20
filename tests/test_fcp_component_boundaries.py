"""FCP preparation/lifecycle characterization; no live model dependency.

These tests use existing processor hooks so they can also run on the stage-two
base. Stage-three extraction must preserve the order observed through them.
"""
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from galet.provider_registry import ProviderRegistry
from src.message_processors import function_calling_processor as fcp
from src.message_processors.fcp_models import ToolHandlerError
from src.message_processors.sse_events import SSEEvent
from src.metrics import CorrelationLogHandler
from src.tool_selection import ToolSelectionError
from tests.conftest import FakeAgent, FakeConfig, FakeHandler, FakeRegistry


@pytest.mark.parametrize("supports_images", [None, False])
def test_preparation_preserves_dependency_hooks_order_and_attachment_arguments(
    monkeypatch, make_proc, supports_images
):
    proc = make_proc()
    order = []
    builder = Mock()
    builder._last_prompt_token_breakdown = {"total_without_handlers": 11, "current_user_message": 4}
    prompt = [{"role": "user", "content": "hello"}]
    builder.build_prompt.side_effect = lambda **kwargs: (order.append("prompt") or prompt)
    builder.storage = object()
    builder.procedural_memory = object()
    adapter = Mock()
    adapter.supports_image_processing.side_effect = lambda *args: (order.append("supports") or True)
    handler = FakeHandler()
    registry = FakeRegistry(handler_by_name={"discover_tools": handler, "activate_tools": handler})
    config = FakeConfig({"provider_prompt_blocks": {"test-provider": "provider instructions"}})
    # Replacements after construction must be visible to preparation and selection.
    proc.prompt_builder = builder
    proc.llm_adapter = adapter
    proc.registry = registry
    proc.config = config
    proc._get_environment_system_messages = lambda: (order.append("environment") or ["custom environment"])
    pipeline = Mock()
    pipeline.get_tool_handler_defs.side_effect = lambda **kwargs: (order.append("tools") or [])
    factory = Mock(return_value=pipeline)
    monkeypatch.setattr(fcp, "ToolSelectionPipeline", factory)
    monkeypatch.setattr(ProviderRegistry, "resolve_name", lambda *args: "test-provider")
    measure = fcp._log_token_breakdown

    def count_tokens(*args):
        order.append("tokens")
        return measure(*args)

    monkeypatch.setattr(fcp, "_log_token_breakdown", count_tokens)
    ctx = SimpleNamespace(
        model="test-model", provider=None, account_id="acct", agent_name="lucy",
        conversation_id="conv", context_type="hybrid", context_name="ctx",
    )
    agent = FakeAgent()
    agent.allowed_tools = ["attachments"]
    for _ in range(2):
        order.clear()
        result = proc._prepare_prompt_and_tools(
            ctx=ctx, primary_agent=agent, message="hello",
            image_ids=["image-1"], file_ids=["file-1"], supports_images=supports_images,
        )
        assert order == (["supports"] if supports_images is None else []) + [
            "environment", "prompt", "tools", "tokens",
        ]
        assert result.prompt_messages is prompt
        assert result.supports_images is (supports_images is None)
        assert result.prompt_breakdown["total"] == 11
        arguments = builder.build_prompt.call_args.kwargs
        messages = arguments["extra_system_messages"]
        assert messages[0] == "custom environment"
        assert "Images uploaded or generated earlier" in messages[1]
        assert "use discover_tools" in messages[2]
        assert messages[3:] == ["provider instructions"]
        assert arguments["image_ids"] == ["image-1"]
        assert arguments["file_ids"] == ["file-1"]
        assert arguments["max_prompt_chars"] == 6000
        factory.assert_called_with(
            registry=registry, storage=builder.storage,
            procedural_memory=builder.procedural_memory, llm_adapter=adapter, config=config,
        )
        pipeline.get_tool_handler_defs.assert_called_with(
            agent=agent, account_name="acct", context_name="ctx", prompt_text="hello",
        )


@pytest.mark.parametrize("value, expected", [
    (None, []), ("  ", []), ({"unexpected": True}, []),
    ("  environment\nblock  ", ["environment\nblock"]),
])
def test_environment_message_hook_reads_current_config_and_returns_fresh_list(make_proc, value, expected):
    proc = make_proc()
    proc.config = FakeConfig({"environment_prompt_block": value})
    first = proc._get_environment_system_messages()
    assert first == expected
    first.append("caller mutation")
    assert proc._get_environment_system_messages() == expected


def configure_run(monkeypatch, make_proc, *, fail_prepare=None):
    proc = make_proc()
    trace = []
    handler = CorrelationLogHandler()
    handler.addFilter(fcp._CorrelationIdFilter())
    proc._correlation_handler = handler
    proc.llm_adapter.supports_image_processing.return_value = False
    logger = Mock()
    proc._metrics_logger = logger

    def append(record):
        # Context restoration precedes the best-effort append.
        assert fcp._correlation_id_var.get() == "outer"
        trace.append("append")

    logger.append.side_effect = append

    def prepare(**kwargs):
        trace.append("prepare")
        if fail_prepare is not None:
            raise fail_prepare
        return SimpleNamespace(
            prompt_messages=[{"role": "user", "content": "hello"}],
            filtered_function_defs=[], supports_images=False, prompt_breakdown={},
        )

    proc._prepare_prompt_and_tools = prepare
    proc.episodic_recorder.write_prompt_report = Mock(side_effect=lambda *a, **k: trace.append("report"))
    proc._write_streaming_episodic_user_message = lambda *a, **k: trace.append("persist:user")
    proc._write_streaming_episodic_events = lambda *a, **k: trace.append("persist:batch")
    proc._write_streaming_episodic_event = lambda ctx, event, **k: trace.append("persist:" + event.type)
    original_finalize = proc._finalize_run

    def finalize(*args, **kwargs):
        trace.append("finalize")
        return original_finalize(*args, **kwargs)

    proc._finalize_run = finalize

    def run(**kwargs):
        trace.append("loop")
        assert fcp._correlation_id_var.get() == "run"
        kwargs["metrics"].update(iterations=2, tool_calls=1, prompt_tokens=10, completion_tokens=4, total_tokens=14)
        warning = logging.LogRecord("probe", logging.WARNING, __file__, 0, "warning", (), None)
        handler.handle(warning)
        yield SSEEvent(type="text", content="hello")
        yield SSEEvent(type="metrics", metrics=dict(kwargs["metrics"]))
        yield SSEEvent(type="done", conversation_id="conv")

    proc.loop_runner.run = run
    return proc, trace, logger, handler


def request():
    return dict(
        primary_agent=FakeAgent(save_responses=True), account={"accountId": "acct"},
        message="hello", conversation_id="conv", context_name="ctx", correlation_id="run",
    )


@pytest.mark.parametrize("streaming", [False, True])
def test_lifecycle_preserves_persistence_delivery_and_context_restoration(monkeypatch, make_proc, streaming):
    proc, trace, logger, handler = configure_run(monkeypatch, make_proc)
    token = fcp._correlation_id_var.set("outer")
    try:
        if streaming:
            generator = proc.process_message_streaming(**request())
            assert trace == []  # Streaming initialization is still lazy.
            assert fcp._correlation_id_var.get() == "outer"
            for wire in generator:
                trace.append("yield:" + json.loads(wire[len("data: "):])["type"])
            assert trace == [
                "prepare", "persist:user", "report", "loop",
                "persist:text", "yield:text", "persist:metrics", "yield:metrics",
                "persist:done", "yield:done", "finalize", "append",
            ]
        else:
            result = proc.process_message(**request())
            assert result.text == "hello"
            assert trace == ["prepare", "report", "loop", "persist:batch", "finalize", "append"]
        assert fcp._correlation_id_var.get() == "outer"
        logger.append.assert_called_once()
        record = logger.append.call_args.args[0]
        assert record.correlation_id == "run"
        assert record.iterations == 2 and record.tool_calls == 1
        assert record.prompt_tokens == 10 and record.completion_tokens == 4 and record.total_tokens == 14
        assert record.warnings == 1 and record.errors == 0
        assert record.success
        assert handler.end_run("run") is None
    finally:
        fcp._correlation_id_var.reset(token)


def test_stream_close_after_text_finalizes_after_persistence(monkeypatch, make_proc):
    proc, trace, logger, handler = configure_run(monkeypatch, make_proc)
    token = fcp._correlation_id_var.set("outer")
    generator = proc.process_message_streaming(**request())
    try:
        wire = next(generator)
        assert json.loads(wire[len("data: "):])["type"] == "text"
        assert trace == ["prepare", "persist:user", "report", "loop", "persist:text"]
        assert fcp._correlation_id_var.get() == "run"
        generator.close()
        assert trace[-2:] == ["finalize", "append"]
        assert fcp._correlation_id_var.get() == "outer"
        logger.append.assert_called_once()
        assert handler.end_run("run") is None
    finally:
        generator.close()
        fcp._correlation_id_var.reset(token)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("failure", ["selection", "handler", "generic"])
def test_prepare_error_finalization_and_sse_error_order(monkeypatch, make_proc, streaming, failure):
    error = {
        "selection": ToolSelectionError("required_not_permissioned", "selection refused"),
        "handler": ToolHandlerError("handler failed"),
        "generic": RuntimeError("prepare failed"),
    }[failure]
    proc, trace, logger, handler = configure_run(monkeypatch, make_proc, fail_prepare=error)
    token = fcp._correlation_id_var.set("outer")
    try:
        if streaming:
            types = []
            def consume():
                for wire in proc.process_message_streaming(**request()):
                    types.append(json.loads(wire[len("data: "):])["type"])
            if failure == "handler":
                with pytest.raises(ToolHandlerError):
                    consume()
            else:
                consume()
            assert types == ["error", "metrics", "done"]
        elif failure == "selection":
            assert proc.process_message(**request()).text == "selection refused"
        else:
            with pytest.raises(type(error)):
                proc.process_message(**request())
        assert trace.count("finalize") == trace.count("append") == 1
        assert "loop" not in trace
        assert fcp._correlation_id_var.get() == "outer"
        logger.append.assert_called_once()
        assert handler.end_run("run") is None
    finally:
        fcp._correlation_id_var.reset(token)


@pytest.mark.parametrize("streaming", [False, True])
def test_metrics_append_failure_does_not_fail_completed_response(monkeypatch, make_proc, streaming):
    proc, trace, logger, handler = configure_run(monkeypatch, make_proc)
    def fail_append(record):
        trace.append("append")
        raise OSError("metrics disk unavailable")
    logger.append.side_effect = fail_append
    token = fcp._correlation_id_var.set("outer")
    try:
        if streaming:
            types = [
                json.loads(wire[len("data: "):])["type"]
                for wire in proc.process_message_streaming(**request())
            ]
            assert types == ["text", "metrics", "done"]
        else:
            assert proc.process_message(**request()).text == "hello"
        assert trace[-2:] == ["finalize", "append"]
        logger.append.assert_called_once()
        assert fcp._correlation_id_var.get() == "outer"
        assert handler.end_run("run") is None
    finally:
        fcp._correlation_id_var.reset(token)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("missing", ["agent", "account"])
def test_early_validation_keeps_finalization_timing(monkeypatch, make_proc, streaming, missing):
    proc, trace, logger, handler = configure_run(monkeypatch, make_proc)
    kwargs = request()
    if missing == "agent":
        kwargs["primary_agent"] = None
    else:
        kwargs["account"] = {"accountId": ""}
    token = fcp._correlation_id_var.set("outer")
    try:
        if streaming:
            for wire in proc.process_message_streaming(**kwargs):
                trace.append("yield:" + json.loads(wire[len("data: "):])["type"])
            assert trace == ["yield:error", "yield:metrics", "yield:done", "finalize", "append"]
        else:
            assert "Missing" in proc.process_message(**kwargs).text
            assert trace == ["finalize", "append"]
        logger.append.assert_called_once()
        record = logger.append.call_args.args[0]
        assert record.processor_failures == record.failures == 1
        assert record.iterations == 0 and record.duration_ms == 0
        assert fcp._correlation_id_var.get() == "outer"
        assert handler.end_run("run") is None
    finally:
        fcp._correlation_id_var.reset(token)
