import json

import src.handlers.execution_trace_handler as trace
from src.handlers.execution_trace_handler import ExecutionTraceHandler
from src.handlers.serve_file_handler import ServeFileHandler
from src.generated_files import resolve_report


CID = "76867d1d-04a0-4f2e-adc3-219a84da9873"


def test_execution_trace_reports_order_timing_and_failures(tmp_path, monkeypatch):
    log = tmp_path / "my_log_file.log"
    log.write_text(
        "2026-10-08 16:58:46,927 - INFO - root - FunctionCallingProcessor(streaming) inbound message: "
        f"correlation_id={CID} message=Inspect task\n"
        "2026-10-08 16:58:47,000 - INFO - root - FunctionCallingProcessor(streaming): start "
        f"correlation_id={CID} account=junwin agent=colin session_id=s1 context_type=none max_iterations=10\n"
        "2026-10-08 16:58:47,100 - INFO - root - Prompt.token_breakdown: "
        "agent=colin account=junwin session=s1 system=100 handlers=200 context=20 "
        "obsidian=0 digest=0 history=0 user=30 total=350\n"
        "2026-10-08 16:58:48,000 - INFO - root - FunctionCallingProcessor(streaming): raw tool calls "
        f"correlation_id={CID} agent=colin session_id=s1 iteration=1 "
        'raw=[{"id": "call_1", "name": "repo_search", "arguments": "{\\"query\\": \\"foo\\", \\"token\\": \\"secret\\"}"}] wrapped=[]\n'
        f"2026-10-08 16:58:48,000 - INFO - root - tool_execute_start correlation_id={CID} tool=repo_search call_id=call_1 account=junwin\n"
        f"2026-10-08 16:58:48,500 - INFO - root - tool_execute_outcome correlation_id={CID} tool=repo_search call_id=call_1 status=failed error_code=not_found result_chars=5000\n"
        f"2026-10-08 16:58:49,200 - INFO - root - model_call_done correlation_id={CID} agent=colin session_id=s1 iteration=1 attempt=1 duration_ms=1200 input_tokens=345 output_tokens=55 total_tokens=400\n"
        f"2026-10-08 16:58:49,000 - INFO - root - tool_execute_done correlation_id={CID} tool=repo_search call_id=call_1 result_preview='{{\"ok\": false, \"error\": \"truncated\n"
        "2026-10-08 16:58:50,000 - INFO - root - FunctionCallingProcessor(streaming): completed "
        f"correlation_id={CID} agent=colin session_id=s1 iterations=1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(trace, "DEFAULT_LOG", log)
    config = {"storage_root_path": str(tmp_path), "storage_namespace": "data"}
    class Config:
        def get(self, key, default=None):
            return config.get(key, default)

    cfg = Config()
    result = ExecutionTraceHandler(cfg).execute(
        {"correlation_id": CID, "format": "json", "include_rotated": False},
        account_name="alice",
    )
    assert result["ok"]
    assert "report" not in result and "formatted" not in result
    file_id = result["file"]["file_id"]
    path, mime = resolve_report(cfg, "alice", file_id)
    assert mime == "application/json"
    assert ServeFileHandler(cfg).execute({"file_id": file_id}, account_name="alice")["ok"]
    assert not ServeFileHandler(cfg).execute({"file_id": file_id}, account_name="bob")["ok"]
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["agent"] == "colin"
    assert report["duration_seconds"] == 3.0
    assert report["tokens"]["prompt_estimate"] == 350
    assert report["tool_calls"][0]["duration_seconds"] == 1.0
    assert report["tool_calls"][0]["status"] == "failed"
    assert report["tool_calls"][0]["error_code"] == "not_found"
    assert report["model_calls"][0]["duration_ms"] == 1200
    assert report["tokens"]["model_usage"]["total_tokens"] == 400
    assert report["tool_calls"][0]["parameters"]["token"] == "[REDACTED]"
    assert result["summary"]["failed_calls"] == 1
    assert result["summary"]["tool_calls"] == 1


def test_execution_trace_rejects_missing_or_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "DEFAULT_LOG", tmp_path / "missing.log")
    h = ExecutionTraceHandler()
    assert not h.execute({"correlation_id": "../something"})["ok"]
    assert not h.execute({"correlation_id": CID})["ok"]
