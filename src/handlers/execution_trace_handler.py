"""Read-only execution trace reconstructed from Lucy's local application logs.

Reports observations, not the model's hidden decision-making.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2
from src.generated_files import save_report
from scripts.log_tools import (
    DEFAULT_LOG, parse_tools, parse_messages, resolve_log_files, iter_lines,
    CORRELATION_RE, timestamp_of,
)

_ID = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9-]{20,}$")
_SUMMARY = re.compile(r"FunctionCallingProcessor summary:.*?iterations=(\d+) openai_calls=(\d+) tool_calls=(\d+) failures=(\d+) latency_ms=(\d+)")
_TOKEN_BREAKDOWN = re.compile(r"Prompt.token_breakdown:.*?system=(\d+) handlers=(\d+) context=(\d+) obsidian=(\d+) digest=(\d+) history=(\d+) user=(\d+) total=(\d+)")
_USAGE = re.compile(r"prompt_tokens=(\d+).*?completion_tokens=(\d+).*?total_tokens=(\d+)")
_OUTCOME = re.compile(r"tool_execute_outcome correlation_id=([\w-]+) tool=(\S+) call_id=(\S+) status=(\S+) error_code=(\S+) result_chars=(\d+)")
_MODEL_CALL = re.compile(r"model_call_done correlation_id=([\w-]+) agent=(\S+) session_id=(\S+) iteration=(\d+) attempt=(\d+) duration_ms=(\d+) input_tokens=(\S+) output_tokens=(\S+) total_tokens=(\S+)")
_SENSITIVE = re.compile(r"(password|secret|api[_-]?key|token|authorization|credential|private[_-]?key)", re.I)


def _redact(value: Any, limit: int) -> Any:
    """Redact sensitive argument names before truncating displayed values."""
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if _SENSITIVE.search(str(k)) else _redact(v, limit))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, limit) for v in value[:20]]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [truncated, {len(value)} chars]"
    return value


def _elapsed(start: str, end: str):
    if not start or not end:
        return None
    try:
        return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3)
    except ValueError:
        return None


def _result_data(preview: str):
    try:
        parsed = json.loads(preview)
        if isinstance(parsed, dict):
            # The application log captures only a preview, not full tool output.
            return _redact(parsed, 240)
    except (TypeError, ValueError):
        pass
    return None


def _status(preview: str, completed: bool):
    if not completed:
        return "incomplete"
    try:
        obj = json.loads(preview)
        if isinstance(obj, dict):
            if obj.get("ok") is False or obj.get("status") == "error":
                return "failed"
            if obj.get("ok") is True:
                return "success"
    except (TypeError, ValueError):
        pass
    return "unknown"


class ExecutionTraceHandler(HandlerV2):
    NAME = "execution_trace"

    def __init__(self, config=None):
        self.config = config

    @classmethod
    def name(cls):
        return cls.NAME

    @classmethod
    def tool_def(cls):
        return {
            "type": "function", "name": cls.NAME,
            "description": "Read Lucy application logs and report a correlation ID's timing, tool calls, parameters, results, failures, and available token usage. No execution or modification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "correlation_id": {"type": "string", "description": "Correlation ID of the run."},
                    "format": {"type": "string", "enum": ["yaml", "json"], "description": "Report serialization."},
                    "include_rotated": {"type": "boolean", "description": "Search rotated log files too."}
                },
                "required": ["correlation_id", "format", "include_rotated"],
                "additionalProperties": False
            },
            "strict": True
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {
            "ok": {"type": "boolean"}, "tool": {"type": "string"},
            "summary": {"type": "object"}, "file": {"type": "object"},
            "error": {"type": "string"}
        }, "required": ["ok", "tool"], "additionalProperties": True}

    def execute(self, args: Dict[str, Any], *, account_name="auto", **context):
        cid = str(args.get("correlation_id") or "").strip()
        if not _ID.fullmatch(cid):
            return {"ok": False, "tool": self.NAME, "error": "Invalid correlation_id"}
        format_name = args.get("format") or "yaml"
        if format_name not in ("json", "yaml"):
            return {"ok": False, "tool": self.NAME, "error": "Invalid format"}
        paths = resolve_log_files(str(DEFAULT_LOG), bool(args.get("include_rotated", True)))
        runs, calls, _ = parse_tools(paths, [cid])
        messages = [m for m in parse_messages(paths) if m.correlation_id == cid]
        run = runs.get(cid, {})
        records = []
        for call in calls.values():
            if call.correlation_id != cid:
                continue
            records.append({
                "call_id": call.call_id,
                "handler": call.tool,
                "start": call.start_ts or None,
                "end": call.done_ts or None,
                "duration_seconds": _elapsed(call.start_ts, call.done_ts),
                "parameters": _redact(call.args, 240),
                "result": _result_data(call.result_preview),
                "result_preview": _redact(call.result_preview, 400),
                "status": _status(call.result_preview, bool(call.done_ts)),
            })
        records.sort(key=lambda item: item["start"] or "")
        prompt_tokens = None
        metrics = {}
        errors = []
        times = []
        outcome_by_call = {}
        model_calls = []
        for line in iter_lines(paths):
            marker = CORRELATION_RE.search(line)
            # Prompt breakdown logs lack a correlation_id. Associate only when
            # agent/session match and timestamp falls within the run interval.
            if (not marker or marker.group(1) != cid):
                token_match = _TOKEN_BREAKDOWN.search(line)
                stamp = timestamp_of(line)
                if (token_match and run.get("agent") and run.get("session_id")
                        and f"agent={run['agent']} " in line
                        and f"session={run['session_id']} " in line
                        and run.get("start_ts") and run.get("done_ts")
                        and run["start_ts"] <= stamp <= run["done_ts"]):
                    prompt_tokens = int(token_match.group(8))
                continue
            stamp = timestamp_of(line)
            if stamp:
                times.append(stamp)
            outcome = _OUTCOME.search(line)
            if outcome:
                outcome_by_call[outcome.group(3)] = {
                    "status": outcome.group(4),
                    "error_code": None if outcome.group(5) == "-" else outcome.group(5),
                    "result_chars": int(outcome.group(6)),
                }
            model_call = _MODEL_CALL.search(line)
            if model_call:
                def _optional_int(value):
                    return None if value == "-" else int(value)
                model_calls.append({
                    "timestamp": stamp, "iteration": int(model_call.group(4)),
                    "attempt": int(model_call.group(5)),
                    "duration_ms": int(model_call.group(6)),
                    "input_tokens": _optional_int(model_call.group(7)),
                    "output_tokens": _optional_int(model_call.group(8)),
                    "total_tokens": _optional_int(model_call.group(9)),
                })
            match = _TOKEN_BREAKDOWN.search(line)
            if match:
                prompt_tokens = int(match.group(8))
            match = _SUMMARY.search(line)
            if match:
                metrics = dict(zip(("iterations", "model_calls", "tool_calls", "failures", "latency_ms"),
                                   map(int, match.groups())))
            if " - ERROR -" in line or " - WARNING -" in line:
                errors.append(_redact(line.split(" - ", 4)[-1], 360))
        for record in records:
            outcome = outcome_by_call.get(record["call_id"])
            if outcome:
                record.update(outcome)
        provider_totals = {
            key: sum(item[key] for item in model_calls if item[key] is not None)
            for key in ("input_tokens", "output_tokens", "total_tokens")
        }
        usage_available = any(item["total_tokens"] is not None for item in model_calls)
        first = run.get("start_ts") or (min(times) if times else None)
        last = run.get("done_ts") or (max(times) if times else None)
        if not records and not messages and not times:
            return {"ok": False, "tool": self.NAME, "error": "Correlation ID not found in available logs"}
        report = {
            "correlation_id": cid,
            "agent": run.get("agent") or None,
            "session_id": run.get("session_id") or None,
            "message": _redact(messages[0].message, 500) if messages else None,
            "start": first, "end": last, "duration_seconds": _elapsed(first, last),
            "tokens": {"prompt_estimate": prompt_tokens,
                       "model_usage": provider_totals if usage_available else None,
                       "note": "Prompt.token_breakdown is an estimate, not billed token usage."},
            "model_calls": model_calls,
            "model_duration_ms": sum(item["duration_ms"] for item in model_calls),
            "metrics": metrics, "tool_calls": records, "errors": errors[:20],
            "limitations": ["Tool result previews may be truncated by application logging.",
                            "Model motivations are not recoverable from tool events alone.",
                            "Success is unknown when the logged preview does not include a structured status."]
        }
        if format_name == "json":
            output = json.dumps(report, indent=2, ensure_ascii=False)
        else:
            try:
                import yaml
                output = yaml.safe_dump(report, sort_keys=False, allow_unicode=True)
            except ImportError:
                # JSON is a valid YAML 1.2 document.
                output = json.dumps(report, indent=2, ensure_ascii=False)
        if self.config is None:
            return {"ok": False, "tool": self.NAME, "error": "Storage configuration unavailable"}
        try:
            file_ref = save_report(self.config, account_name, output, format_name)
        except (ValueError, OSError) as exc:
            return {"ok": False, "tool": self.NAME, "error": str(exc)}
        calls = records
        return {
            "ok": True, "tool": self.NAME,
            "correlation_id": cid,
            "summary": {
                "agent": report["agent"],
                "duration_seconds": report["duration_seconds"],
                "tool_calls": len(calls),
                "failed_calls": sum(call["status"] == "failed" for call in calls),
                "unknown_calls": sum(call["status"] == "unknown" for call in calls),
                "prompt_token_estimate": prompt_tokens,
                "model_calls": len(model_calls),
                "model_duration_ms": sum(item["duration_ms"] for item in model_calls),
                "model_tokens": provider_totals if usage_available else None,
            },
            "file": file_ref,
        }
