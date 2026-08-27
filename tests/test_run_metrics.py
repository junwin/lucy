"""RunMetrics round-trip, hit_iteration_cap flag, and FCPResult tests (design tests 1-4, 9-10)."""

import pytest

from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics


def test_run_metrics_round_trip():
    m = RunMetrics(
        correlation_id="corr-1",
        iterations=3,
        max_iterations=5,
        hit_iteration_cap=True,
        openai_calls=4,
        tool_calls=2,
        prompt_tokens=100,
        completion_tokens=50,
        failures=1,
        duration_ms=1234,
        agent="lucy",
        account="junwin",
        session_id="sess-1",
        started="2026-08-27T14:00:00.000Z",
        errors=2,
        warnings=1,
        success=False,
    )
    d = m.to_dict()
    assert d["total_tokens"] == 150
    assert d["agent"] == "lucy"
    assert d["account"] == "junwin"
    assert d["session_id"] == "sess-1"
    assert d["started"] == "2026-08-27T14:00:00.000Z"
    assert d["errors"] == 2
    assert d["warnings"] == 1
    assert d["success"] is False
    m2 = RunMetrics.from_dict(d)
    assert m2.to_dict() == d


def test_run_metrics_total_tokens_derived_when_absent():
    m = RunMetrics.from_dict({"prompt_tokens": 10, "completion_tokens": 7})
    assert m.total_tokens == 17
    assert m.to_dict()["total_tokens"] == 17


def test_run_metrics_from_dict_defaults_envelope_fields():
    m = RunMetrics.from_dict({"correlation_id": "corr-x", "failures": 0})
    assert m.agent == ""
    assert m.account == ""
    assert m.session_id == ""
    assert m.started == ""
    assert m.errors == 0
    assert m.warnings == 0
    assert m.success is True


def test_run_metrics_defaults():
    m = RunMetrics()
    assert m.to_dict() == {
        "correlation_id": "",
        "iterations": 0,
        "max_iterations": 0,
        "hit_iteration_cap": False,
        "openai_calls": 0,
        "tool_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "failures": 0,
        "duration_ms": 0,
        "agent": "",
        "account": "",
        "session_id": "",
        "started": "",
        "errors": 0,
        "warnings": 0,
        "success": True,
    }


def test_run_metrics_strict_validation_rejects_unknown_field():
    with pytest.raises(ValueError):
        RunMetrics.from_dict({"unknown": 1})


def test_run_metrics_from_dict_requires_dict():
    with pytest.raises(TypeError):
        RunMetrics.from_dict("not-a-dict")


def test_hit_iteration_cap_flag(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent, FakeHandler, FakeRegistry, setup_no_tool_calls

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)
    captured = {}
    orig_run = proc.loop_runner.run

    def spy_run(**kwargs):
        captured["metrics"] = kwargs["metrics"]
        yield from orig_run(**kwargs)

    proc.loop_runner.run = spy_run

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "loop"}]
    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{}",
    }

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=1),
        account={"accountId": "acct1"},
        message="loop",
        conversation_id="c1",
        context_name="ctx",
    )

    assert "internal limit" in out.text.lower()
    assert out.metrics.hit_iteration_cap is True
    assert out.metrics.failures == 1
    assert captured["metrics"]["hit_iteration_cap"] is True
    assert captured["metrics"]["failures"] == 1

    setup_no_tool_calls(llm_adapter, text="ok")
    out = proc.process_message(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out.text == "ok"
    assert out.metrics.hit_iteration_cap is False
    assert captured["metrics"]["hit_iteration_cap"] is False


def test_streaming_initializes_hit_iteration_cap_false(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent

    proc = make_proc()
    captured = {}
    orig_run = proc.loop_runner.run

    def spy_run(**kwargs):
        captured["metrics"] = kwargs["metrics"]
        yield from orig_run(**kwargs)

    proc.loop_runner.run = spy_run

    events = list(
        proc.process_message_streaming(
            primary_agent=FakeAgent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="ctx",
        )
    )

    assert captured["metrics"]["hit_iteration_cap"] is False
    assert events


def test_fcp_result_returns_metrics(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent, FakeHandler, FakeRegistry, setup_no_tool_calls

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "loop"}]
    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{}",
    }

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=1),
        account={"accountId": "acct1"},
        message="loop",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-cap",
    )

    assert isinstance(out, FCPResult)
    assert "internal limit" in out.text.lower()
    assert out.metrics.correlation_id == "corr-cap"
    assert out.metrics.iterations == 1
    assert out.metrics.max_iterations == 1
    assert out.metrics.hit_iteration_cap is True
    assert out.metrics.openai_calls == 1
    assert out.metrics.tool_calls == 1
    assert out.metrics.failures == 1
    assert out.metrics.prompt_tokens == 0
    assert out.metrics.completion_tokens == 0
    assert out.metrics.total_tokens == 0
    assert out.metrics.duration_ms >= 0

    setup_no_tool_calls(llm_adapter, text="ok")
    out = proc.process_message(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-ok",
    )

    assert isinstance(out, FCPResult)
    assert out.text == "ok"
    assert out.metrics.correlation_id == "corr-ok"
    assert out.metrics.iterations == 1
    assert out.metrics.max_iterations == 5
    assert out.metrics.hit_iteration_cap is False
    assert out.metrics.openai_calls == 1
    assert out.metrics.tool_calls == 0
    assert out.metrics.failures == 0
    assert out.metrics.duration_ms >= 0


def test_fcp_result_tool_selection_error(make_proc):
    from tests.conftest import FakeAgent
    from src.tool_selection import ToolSelectionError

    proc = make_proc()

    def raise_selection_error(**kwargs):
        raise ToolSelectionError("required_not_permissioned", "selection failed")

    proc._prepare_prompt_and_tools = raise_selection_error

    out = proc.process_message(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-sel",
    )

    assert isinstance(out, FCPResult)
    assert out.text == "selection failed"
    assert out.metrics.correlation_id == "corr-sel"
    assert out.metrics.failures == 1
    assert out.metrics.duration_ms >= 0


def test_fcp_result_early_returns(make_proc):
    from tests.conftest import FakeAgent

    proc = make_proc()

    out = proc.process_message(
        primary_agent=None,
        account={"accountId": "acct1"},
        message="hi",
        correlation_id="corr-early-1",
    )

    assert isinstance(out, FCPResult)
    assert out.text == "[FunctionCallingProcessor] Missing primary_agent configuration."
    assert out.metrics.correlation_id == "corr-early-1"
    assert out.metrics.failures == 1
    assert out.metrics.iterations == 0
    assert out.metrics.max_iterations == 0
    assert out.metrics.hit_iteration_cap is False
    assert out.metrics.openai_calls == 0
    assert out.metrics.tool_calls == 0
    assert out.metrics.duration_ms == 0

    out = proc.process_message(
        primary_agent=FakeAgent(),
        account={"accountId": ""},
        message="hi",
        correlation_id="corr-early-2",
    )

    assert isinstance(out, FCPResult)
    assert out.text == "[FunctionCallingProcessor] Missing account.accountId."
    assert out.metrics.correlation_id == "corr-early-2"
    assert out.metrics.failures == 1
    assert out.metrics.iterations == 0
    assert out.metrics.max_iterations == 0
    assert out.metrics.hit_iteration_cap is False
    assert out.metrics.openai_calls == 0
    assert out.metrics.tool_calls == 0
    assert out.metrics.duration_ms == 0


def _parse_sse(events):
    import json
    return [json.loads(e[len("data: "):].strip()) for e in events]


def test_streaming_emits_metrics_event(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent, FakeHandler, FakeRegistry, setup_no_tool_calls

    proc = make_proc()

    def run_stream(**kwargs):
        return _parse_sse(list(proc.process_message_streaming(**kwargs)))

    setup_no_tool_calls(llm_adapter, text="ok")
    events = run_stream(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-stream-ok",
    )
    assert events[-1]["type"] == "done"
    assert events[-2]["type"] == "metrics"
    m = events[-2]["metrics"]
    assert m["iterations"] == 1
    assert m["openai_calls"] == 1
    assert m["tool_calls"] == 0
    assert m["failures"] == 0
    assert m["hit_iteration_cap"] is False

    llm_adapter.reset_mock()
    resp = object()
    llm_adapter.call_model.return_value = resp
    llm_adapter.get_response_id.return_value = None
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.get_text.return_value = ""

    events = run_stream(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-stream-noid",
    )
    assert any(e["type"] == "error" for e in events)
    assert events[-1]["type"] == "done"
    assert events[-2]["type"] == "metrics"
    m = events[-2]["metrics"]
    assert m["iterations"] == 1
    assert m["openai_calls"] == 1
    assert m["tool_calls"] == 0
    assert m["failures"] == 1

    handler = FakeHandler({"ok": True}, exc=RuntimeError("boom"))
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)

    llm_adapter.reset_mock()
    resp = object()
    llm_adapter.call_model.return_value = resp
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.get_text.return_value = ""

    events = run_stream(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-stream-toolerr",
    )
    assert any(e["type"] == "error" for e in events)
    assert events[-1]["type"] == "done"
    assert events[-2]["type"] == "metrics"
    m = events[-2]["metrics"]
    assert m["iterations"] == 1
    assert m["openai_calls"] == 1
    assert m["tool_calls"] == 1
    assert m["failures"] == 1


def test_streaming_error_paths_emit_metrics(make_proc, prompt_builder, llm_adapter):
    import pytest
    from tests.conftest import FakeAgent
    from src.message_processors.fcp_models import ToolHandlerError
    from src.tool_selection import ToolSelectionError

    proc = make_proc()

    def assert_metrics_before_done(events, failures):
        assert events[-1]["type"] == "done"
        assert events[-2]["type"] == "metrics"
        assert events[-2]["metrics"]["failures"] == failures

    events = _parse_sse(list(proc.process_message_streaming(
        primary_agent=None,
        account={"accountId": "acct1"},
        message="hi",
        correlation_id="corr-s-early-1",
    )))
    assert any(e["type"] == "error" for e in events)
    assert_metrics_before_done(events, failures=1)
    assert events[-2]["metrics"] == {
        "iterations": 0,
        "openai_calls": 0,
        "tool_calls": 0,
        "failures": 1,
        "hit_iteration_cap": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    events = _parse_sse(list(proc.process_message_streaming(
        primary_agent=FakeAgent(),
        account={"accountId": ""},
        message="hi",
        correlation_id="corr-s-early-2",
    )))
    assert any(e["type"] == "error" for e in events)
    assert_metrics_before_done(events, failures=1)

    def raise_handler_error(**kwargs):
        raise ToolHandlerError("tool boom")

    proc._prepare_prompt_and_tools = raise_handler_error

    events = []
    with pytest.raises(ToolHandlerError):
        for sse in proc.process_message_streaming(
            primary_agent=FakeAgent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="ctx",
            correlation_id="corr-s-handler",
        ):
            events.append(sse)
    assert_metrics_before_done(_parse_sse(events), failures=0)

    def raise_selection_error(**kwargs):
        raise ToolSelectionError("required_not_permissioned", "selection failed")

    proc._prepare_prompt_and_tools = raise_selection_error

    events = _parse_sse(list(proc.process_message_streaming(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-s-selection",
    )))
    assert any(e["type"] == "error" for e in events)
    assert_metrics_before_done(events, failures=1)

    def raise_generic_error(**kwargs):
        raise RuntimeError("boom")

    proc._prepare_prompt_and_tools = raise_generic_error

    events = _parse_sse(list(proc.process_message_streaming(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-s-exc",
    )))
    assert any(e["type"] == "error" for e in events)
    assert_metrics_before_done(events, failures=1)


def test_loop_accumulates_token_usage(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent, FakeHandler, FakeRegistry
    from galet.dto import LLMUsage

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "loop"}]
    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{}",
    }
    llm_adapter.get_usage.return_value = LLMUsage(
        input_tokens=100, output_tokens=20, total_tokens=120
    )

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=2),
        account={"accountId": "acct1"},
        message="loop",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-tokens",
    )

    assert out.metrics.iterations == 2
    assert out.metrics.prompt_tokens == 200
    assert out.metrics.completion_tokens == 40
    assert out.metrics.total_tokens == 240


def test_usage_none_leaves_tokens_zero(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent, setup_no_tool_calls

    proc = make_proc()
    setup_no_tool_calls(llm_adapter, text="ok")
    llm_adapter.get_usage.return_value = None

    out = proc.process_message(
        primary_agent=FakeAgent(),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
        correlation_id="corr-tokens-none",
    )

    assert out.metrics.prompt_tokens == 0
    assert out.metrics.completion_tokens == 0
    assert out.metrics.total_tokens == 0
