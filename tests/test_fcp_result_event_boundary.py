"""Loop/event characterization for #279 stage 4, without a live model.

All tests use the pre-existing loop interface/inspection hook, allowing the same
file to run on the stage-three base before validating the extraction.
"""
import json
from types import SimpleNamespace

import pytest
from galet.dto import LLMUsage
from galet.provider_registry import ProviderRegistry

from src.message_processors.fcp_loop import LLMLoopRunner
from src.message_processors.fcp_models import ProcessorContext, _ToolCall, ToolHandlerError, ToolResultTooLargeError
from tests.conftest import FakeConfig


def response(text="", calls=None, response_id="r1"):
    return {"text": text, "calls": calls or [], "id": response_id}


def make_loop(monkeypatch, responses, raw_results, outputs, *, max_iterations=3, failure=None):
    trace, model_calls = [], []
    scripted = iter(responses)

    def call_model(**kwargs):
        trace.append("model")
        model_calls.append({**kwargs, "input": list(kwargs["input"]), "tools": list(kwargs["tools"])})
        return next(scripted)

    adapter = SimpleNamespace(
        call_model=call_model, get_response_id=lambda value: value["id"],
        get_text=lambda value: value["text"], extract_tool_calls=lambda value: value["calls"],
        get_usage=lambda value: LLMUsage(input_tokens=1, output_tokens=2, total_tokens=3),
    )

    def execute_tool_calls(**kwargs):
        trace.append("execute")
        kwargs["metrics"]["tool_calls"] += len(kwargs["tool_calls"])
        if failure is not None:
            raise failure
        return outputs, raw_results

    def activate(**kwargs):
        trace.append("activate")
        kwargs["function_defs"].append({"name": "activated"})
        return ["activated"]

    executor = SimpleNamespace(
        wrap_tool_calls=lambda values: values, execute_tool_calls=execute_tool_calls,
        apply_tool_activations=activate,
    )
    monkeypatch.setattr(ProviderRegistry, "resolve_name", lambda *args: "test-provider")
    runner = LLMLoopRunner(llm_adapter=adapter, config=FakeConfig(), tool_executor=executor)
    ctx = ProcessorContext(
        account_id="acct", agent_name="worker", conversation_id="conv", context_name="ctx",
        model="test-model", temperature=0, context_type="hybrid", max_iterations=max_iterations,
        store_this_call=False, delegation_depth=0,
    )
    metrics = dict(
        iterations=0, openai_calls=0, tool_calls=0, failures=0, tool_failures=0,
        processor_failures=0, hit_iteration_cap=False, prompt_tokens=0,
        completion_tokens=0, total_tokens=0,
    )
    generator = runner.run(
        ctx=ctx, prompt_messages=[{"role": "user", "content": "hello"}],
        function_defs=[{"name": "initial"}], primary_agent=SimpleNamespace(name="worker"),
        secondary_agent=None, processor_factory=None, account={"accountId": "acct"},
        metrics=metrics, correlation_id="run", trace_id="root",
    )
    return generator, metrics, trace, model_calls


@pytest.mark.parametrize("raw, ok, status", [
    ("{}", True, "success"),
    ('{"ok": false}', False, "error"),
    ('{"status": "warning"}', True, "warning"),
    ('{"ok": false, "status": "warning"}', False, "warning"),
    ('{"status": "unknown"}', True, "success"),
    ('{"ok": null}', None, "error"),
    ("not JSON", True, "success"),
    ("[]", True, "success"),
    (None, True, "success"),
])
def test_status_events_keep_existing_decoding_and_output_call_id(monkeypatch, raw, ok, status):
    call = _ToolCall(name="probe", call_id="request-id", arguments_raw="{}")
    output = {"type": "function_call_output", "call_id": "output-id", "output": raw}
    gen, _, _, _ = make_loop(
        monkeypatch, [response(calls=[call]), response(text="done", response_id="r2")],
        [(call, raw)], [output],
    )
    statuses = [event for event in gen if event.type == "tool_result"]
    assert len(statuses) == 1
    assert statuses[0].call_id == "output-id"
    assert statuses[0].ok is ok
    assert statuses[0].status == status


def test_all_statuses_precede_deliverables_activation_and_continuation(monkeypatch):
    first = _ToolCall(name="execution_trace", call_id="c1", arguments_raw="{}")
    second = _ToolCall(name="probe", call_id="c2", arguments_raw="{}")
    payload = {
        "ok": True, "status": "warning", "action": "redirect", "action_payload": {"url": "/"},
        "image": {"url": "data:image/png;base64,eA==", "alt": "preview"},
        "file": {"file_id": "file-1", "size_bytes": 12},
        "video": {"url": "/video.mp4", "video_id": "video-1"},
    }
    raw = [(first, json.dumps(payload)), (second, '{"ok":false,"image":{"url":"/hidden.png"}}')]
    outputs = [{"type": "function_call_output", "call_id": call.call_id, "output": value} for call, value in raw]
    gen, metrics, trace, calls = make_loop(
        monkeypatch,
        [response("working", [first, second]), response("done", response_id="r2")], raw, outputs,
    )
    events = []
    for _ in range(9):
        events.append(next(gen))
    assert [e.type for e in events] == [
        "text", "tool_call", "tool_call", "tool_result", "tool_result", "action", "image", "file", "video",
    ]
    assert trace == ["model", "execute"]
    assert [e.status for e in events if e.type == "tool_result"] == ["warning", "error"]
    events.extend(gen)
    assert [e.type for e in events[-3:]] == ["text", "metrics", "done"]
    assert trace == ["model", "execute", "activate", "model"]
    assert calls[1]["input"] == outputs
    assert calls[1]["previous_response_id"] == "r1"
    assert calls[1]["tools"] == [{"name": "initial"}, {"name": "activated"}]
    assert metrics["iterations"] == metrics["openai_calls"] == metrics["tool_calls"] == 2
    assert metrics["prompt_tokens"] == 2 and metrics["completion_tokens"] == 4 and metrics["total_tokens"] == 6


def test_payload_event_order_svg_priority_and_generated_image_short_circuit():
    call = _ToolCall(name="serve_file", call_id="c1", arguments_raw="{}")
    payload = {
        "action": "reset_session", "svg": {"markup": "<svg/>", "width": 10},
        "image": {"url": "/not-used.png"}, "file": {"file_id": "f1"},
        "video": {"url": "/v.mp4"},
    }
    events = list(LLMLoopRunner._inspect_raw_results([(call, json.dumps(payload))]))
    assert [e.type for e in events] == ["action", "image", "file", "video"]
    assert events[1].format == "svg" and events[1].svg_markup == "<svg/>"
    assert events[2].download_name == "report.yaml"
    assert events[2].mime_type == "application/octet-stream"
    generated = _ToolCall(name="image_generate", call_id="c2", arguments_raw="{}")
    payload["image_id"] = "image-1"
    generated_events = list(LLMLoopRunner._inspect_raw_results([(generated, json.dumps(payload))]))
    assert len(generated_events) == 1
    assert generated_events[0].image_ref == {"image_id": "image-1"}
    assert generated_events[0].message_id == "image:image-1"


@pytest.mark.parametrize("name, allowed", [
    ("execution_trace", True), ("tasklist_dryrun", True), ("serve_file", True), ("unrelated", False),
])
def test_report_file_allowlist_is_preserved(name, allowed):
    call = _ToolCall(name=name, call_id="c", arguments_raw="{}")
    events = list(LLMLoopRunner._inspect_raw_results([(call, '{"file":{"file_id":"f"}}')]))
    assert [e.type for e in events] == (["file"] if allowed else [])


@pytest.mark.parametrize("raw", ["broken", "[]", "null", "42", None, '{"ok":false,"action":"reset_session"}'])
def test_malformed_nonobject_and_failed_payloads_have_no_deliverables(raw):
    assert list(LLMLoopRunner._inspect_raw_results([(None, raw)])) == []


def test_empty_response_retries_preserve_usage_iteration_and_response_chaining(monkeypatch):
    gen, metrics, trace, calls = make_loop(
        monkeypatch,
        [response(response_id="empty-1"), response(response_id="empty-2"), response("done", response_id="final")],
        [], [], max_iterations=1,
    )
    assert [e.type for e in gen] == ["text", "metrics", "done"]
    assert trace == ["model"] * 3
    assert metrics["iterations"] == 1 and metrics["openai_calls"] == 3
    assert metrics["prompt_tokens"] == 3 and metrics["completion_tokens"] == 6 and metrics["total_tokens"] == 9
    assert [call["previous_response_id"] for call in calls] == [None, "empty-1", "empty-2"]
    assert all(call["input"] == [{"role": "user", "content": "hello"}] for call in calls)
    assert not metrics["hit_iteration_cap"]


def test_duplicate_calls_do_not_execute_twice(monkeypatch):
    call = _ToolCall(name="probe", call_id="c1", arguments_raw="{}")
    duplicate = _ToolCall(name="probe", call_id="c2", arguments_raw="{}")
    raw = [(call, '{"ok":true}')]
    output = [{"call_id": "c1", "output": raw[0][1]}]
    gen, metrics, trace, _ = make_loop(
        monkeypatch,
        [response(calls=[call]), response(calls=[duplicate], response_id="r2")], raw, output,
    )
    events = list(gen)
    assert trace.count("execute") == 1
    assert sum(e.type == "tool_call" for e in events) == 1
    assert metrics["iterations"] == 2 and metrics["openai_calls"] == 2
    assert any(e.type == "text" and "repeating" in e.content for e in events)
    assert not metrics["hit_iteration_cap"]


def test_iteration_cap_still_runs_activation_but_never_another_model_call(monkeypatch):
    call = _ToolCall(name="probe", call_id="c1", arguments_raw="{}")
    gen, metrics, trace, _ = make_loop(
        monkeypatch, [response(calls=[call])], [(call, '{"ok":true}')],
        [{"call_id": "c1", "output": "{}"}], max_iterations=1,
    )
    events = list(gen)
    assert trace == ["model", "execute", "activate"]
    assert metrics["hit_iteration_cap"]
    assert metrics["processor_failures"] == metrics["failures"] == 1
    assert any(e.type == "text" and "internal limit" in e.content for e in events)


def test_missing_response_id_stops_before_execution(monkeypatch):
    call = _ToolCall(name="probe", call_id="c1", arguments_raw="{}")
    gen, metrics, trace, _ = make_loop(
        monkeypatch, [response(calls=[call], response_id=None)], [], [],
    )
    assert [e.type for e in gen] == ["error", "metrics", "done"]
    assert trace == ["model"]
    assert metrics["processor_failures"] == metrics["failures"] == 1


@pytest.mark.parametrize("failure", [ToolHandlerError("failed"), ToolResultTooLargeError("too large")])
def test_execution_errors_emit_failed_results_and_stop_before_activation(monkeypatch, failure):
    calls = [_ToolCall(name="probe", call_id="c1", arguments_raw="{}"),
             _ToolCall(name="probe", call_id="c2", arguments_raw='{"different":true}')]
    gen, _, trace, _ = make_loop(
        monkeypatch, [response(calls=calls)], [], [], failure=failure,
    )
    events = list(gen)
    assert [e.type for e in events] == ["tool_call", "tool_call", "tool_result", "tool_result", "error", "metrics", "done"]
    assert [e.ok for e in events if e.type == "tool_result"] == [False, False]
    assert events[-3].message == str(failure)
    assert trace == ["model", "execute"]
