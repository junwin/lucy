"""SSEEvent metrics event type validation (design test 11)."""

import pytest

from src.message_processors.sse_events import SSEEvent


def test_sse_metrics_event_type_validates():
    payload = {"iterations": 3, "tool_calls": 2, "hit_iteration_cap": True}
    event = SSEEvent(type="metrics", metrics=payload)
    assert event.type == "metrics"
    assert event.metrics == payload


def test_sse_metrics_defaults_to_none():
    event = SSEEvent(type="metrics")
    assert event.metrics is None


def test_sse_metrics_event_serializes_payload():
    event = SSEEvent(type="metrics", metrics={"failures": 1})
    assert '"type":"metrics"' in event.to_sse()
    assert '"metrics":{"failures":1}' in event.to_sse()


def test_sse_existing_event_types_unaffected():
    text_event = SSEEvent(type="text", content="hello")
    assert text_event.metrics is None

    tool_call = SSEEvent(type="tool_call", tool_name="execute_command", call_id="c1")
    assert tool_call.type == "tool_call"

    done = SSEEvent(type="done", conversation_id="conv-1")
    assert done.type == "done"

    error = SSEEvent(type="error", message="boom")
    assert error.type == "error"


def test_sse_unknown_type_rejected():
    with pytest.raises(Exception):
        SSEEvent(type="not_a_real_type")
