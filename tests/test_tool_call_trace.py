"""ToolCallTrace round-trip and strict-validation tests (issue #204, recommendation 5)."""

import hashlib
import json

import pytest

from src.metrics import ToolCallTraceLogger
from src.metrics.tool_call_digest import (
    args_digest,
    error_code,
    error_signature,
    normalize_args,
)
from src.metrics.tool_call_trace import ToolCallTrace


def test_tool_call_trace_round_trip():
    t = ToolCallTrace(
        correlation_id="corr-1",
        parent_correlation_id="corr-0",
        iteration=2,
        tool_name="read_file",
        call_id="call-abc",
        args_digest="deadbeef",
        ok=False,
        error_code="tool_error",
        error_signature="sig-123",
        duration_ms=42,
        ts="2026-09-21T14:00:00.000Z",
    )
    d = t.to_dict()
    assert d["parent_correlation_id"] == "corr-0"
    assert d["error_code"] == "tool_error"
    assert d["error_signature"] == "sig-123"

    restored = ToolCallTrace.from_dict(d)
    assert restored.to_dict() == d


def test_tool_call_trace_optional_fields_round_trip_as_none():
    t = ToolCallTrace(correlation_id="corr-2", tool_name="write_file")
    d = t.to_dict()
    assert d["parent_correlation_id"] is None
    assert d["error_code"] is None
    assert d["error_signature"] is None

    restored = ToolCallTrace.from_dict(d)
    assert restored.parent_correlation_id is None
    assert restored.error_code is None
    assert restored.error_signature is None
    assert restored.to_dict() == d


def test_tool_call_trace_defaults():
    assert ToolCallTrace().to_dict() == {
        "correlation_id": "",
        "parent_correlation_id": None,
        "iteration": 0,
        "tool_name": "",
        "call_id": "",
        "args_digest": "",
        "ok": True,
        "error_code": None,
        "error_signature": None,
        "duration_ms": 0,
        "ts": "",
    }


def test_tool_call_trace_strict_validation_rejects_unknown_field():
    with pytest.raises(ValueError):
        ToolCallTrace.from_dict({"unknown": 1})


def test_tool_call_trace_from_dict_requires_dict():
    with pytest.raises(TypeError):
        ToolCallTrace.from_dict(["not", "a", "dict"])


def test_tool_call_args_digest_helpers():
    shuffled = '{"b":1,"a":{"y":2,"x":[{"q":1,"p":2}]}}'
    ordered = '{"a":{"x":[{"p":2,"q":1}],"y":2},"b":1}'

    assert normalize_args(shuffled) == normalize_args(ordered)
    assert normalize_args(shuffled) == ordered
    assert args_digest(shuffled) == args_digest(ordered)


def test_tool_call_args_digest_nested_key_order_is_stable():
    first = '{"outer":{"inner":[{"z":1,"a":2},{"m":3,"b":4}]},"top":5}'
    second = '{"top":5,"outer":{"inner":[{"a":2,"z":1},{"b":4,"m":3}]}}'

    assert normalize_args(first) == normalize_args(second)
    assert args_digest(first) == args_digest(second)
    assert normalize_args(first) == '{"outer":{"inner":[{"a":2,"z":1},{"b":4,"m":3}]},"top":5}'


def test_tool_call_args_digest_raw_string_fallback():
    raw = "not-json {oops"

    assert normalize_args(raw) == raw
    assert args_digest(raw) == hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def test_tool_call_args_digest_unicode_is_not_escaped():
    encoded = '{"name":"caf\\u00e9 \\u2713"}'
    literal = '{"name":"caf\u00e9 \u2713"}'

    assert normalize_args(encoded) == '{"name":"caf\u00e9 \u2713"}'
    assert "\\u00e9" not in normalize_args(encoded)
    assert normalize_args(encoded) == normalize_args(literal)
    assert args_digest(encoded) == args_digest(literal)


def test_tool_call_args_digest_is_deterministic_16_hex():
    raw = '{"path":"/tmp/x","limit":10}'
    first = args_digest(raw)
    second = args_digest(raw)

    assert first == second
    assert len(first) == 16
    assert first == first.lower()
    assert all(char in "0123456789abcdef" for char in first)


def test_tool_call_error_digest_helpers():
    unknown_tool = json.dumps(
        {"ok": False, "tool": "bash", "error": "Unknown tool 'bash'. Valid tools: ['read_file']"},
        ensure_ascii=False,
    )
    too_large = json.dumps(
        {
            "ok": False,
            "tool": "read_file",
            "error": "Tool result too large: 12000 chars (limit 10000)",
        },
        ensure_ascii=False,
    )
    refused = json.dumps(
        {
            "ok": False,
            "tool": "execute_command",
            "status": "error",
            "error_code": "policy_refused",
            "error": "Execution refused by security policy",
        },
        ensure_ascii=False,
    )
    handler_error = json.dumps({"ok": False, "error": "ValueError: nope"}, ensure_ascii=False)

    assert error_code(unknown_tool) == "unknown_tool"
    assert error_code(too_large) == "result_too_large"
    assert error_code(refused) == "security_refusal"
    assert error_code(handler_error) == "tool_handler_error"


def test_tool_call_error_code_requires_explicit_ok_false():
    assert error_code(json.dumps({"ok": True, "error": "Unknown tool 'bash'"})) is None
    assert error_code(json.dumps({"error": "Unknown tool 'bash'"})) is None
    assert error_code(json.dumps({"ok": "false", "error": "Unknown tool 'bash'"})) is None
    assert error_code(json.dumps(["not", "a", "dict"])) is None
    assert error_code(json.dumps(None)) is None
    assert error_code("") is None
    assert error_code("not-json {oops") is None


def test_tool_call_error_code_uses_result_shapes():
    image_too_large = json.dumps(
        {
            "ok": False,
            "tool": "serve_image",
            "error": "Image too large for tool result (45000 chars, limit 10000). "
            "Please retry with max_dimension=512 or smaller.",
        },
        ensure_ascii=False,
    )
    path_refused = json.dumps({"ok": False, "error": "File access outside allowed base path"})
    refused_by_policy = json.dumps(
        {"ok": False, "tool": "execute_command", "error": "Execution refused by security policy"}
    )
    permission_denied = json.dumps(
        {
            "ok": False,
            "tool": "execute_command",
            "error_code": "permission_denied",
            "error": "Permission denied while starting 'x'.",
        }
    )
    returned_none = json.dumps({"ok": False, "error": "Tool returned None"})
    not_serializable = json.dumps({"ok": False, "error": "Tool result not serializable: circular"})

    assert error_code(image_too_large) == "result_too_large"
    assert error_code(path_refused) == "security_refusal"
    assert error_code(refused_by_policy) == "security_refusal"
    assert error_code(permission_denied) == "security_refusal"
    assert error_code(returned_none) == "tool_handler_error"
    assert error_code(not_serializable) == "tool_handler_error"


def test_tool_call_error_code_other_fallback():
    assert error_code(json.dumps({"ok": False, "error": "Image not found: /tmp/x.png"})) == "other"
    assert error_code(json.dumps({"ok": False})) == "other"
    assert error_code(json.dumps({"ok": False, "error": ""})) == "other"


def test_tool_call_error_signature_normalizes_text():
    noisy = "  ValueError:   NOPE!!  "
    quiet = "valueerror: nope"

    assert error_signature(noisy) == error_signature(quiet)
    assert error_signature(noisy) == hashlib.sha256(b"valueerror: nope").hexdigest()[:16]


def test_tool_call_error_signature_collapses_whitespace():
    multiline = """ValueError:
    nope"""
    spaced = "valueerror: nope"

    assert error_signature(multiline) == error_signature(spaced)


def test_tool_call_error_signature_keeps_internal_punctuation():
    first = "Tool result too large: 12000 chars (limit 10000)."
    second = "Tool result too large: 12001 chars (limit 10000)!"

    assert error_signature(first) != error_signature(second)
    assert error_signature(first) == error_signature("Tool result too large: 12000 chars (limit 10000)")


def test_tool_call_error_signature_none_and_empty_inputs():
    assert error_signature("") is None
    assert error_signature("   ") is None
    assert error_signature("!!!") is None


def test_tool_call_error_signature_is_deterministic_16_hex():
    text = "Unknown tool 'bash'. Valid tools: ['read_file']"
    first = error_signature(text)
    second = error_signature(text)

    assert first == second
    assert len(first) == 16
    assert first == first.lower()
    assert all(char in "0123456789abcdef" for char in first)


def test_tool_call_trace_logger_appends(tmp_path):
    path = tmp_path / "metrics" / "nested" / "tool_calls.jsonl"
    logger = ToolCallTraceLogger(path)
    record = ToolCallTrace(
        correlation_id="corr-1",
        parent_correlation_id="corr-0",
        iteration=2,
        tool_name="read_file",
        call_id="call-abc",
        args_digest="deadbeef",
        ok=False,
        error_code="tool_error",
        error_signature="sig-123",
        duration_ms=42,
        ts="2026-09-21T14:00:00.000Z",
    )

    logger.append(record)

    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record.to_dict()
    assert ": " not in lines[0]


def test_tool_call_trace_logger_appends_one_line_per_call(tmp_path):
    path = tmp_path / "metrics" / "tool_calls.jsonl"
    logger = ToolCallTraceLogger(path)

    logger.append(ToolCallTrace(correlation_id="corr-1", tool_name="read_file"))
    logger.append(ToolCallTrace(correlation_id="corr-2", tool_name="write_file", ok=False))

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["tool_name"] == "read_file"
    assert json.loads(lines[1])["tool_name"] == "write_file"
    assert json.loads(lines[1])["ok"] is False
