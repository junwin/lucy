from src.generated_files import resolve_report, save_report
from src.handlers.serve_file_handler import ServeFileHandler
from src.message_processors.fcp_loop import LLMLoopRunner
from src.message_processors.fcp_models import _ToolCall
import json
import pytest


class Config:
    def __init__(self, root):
        self.root = str(root)

    def get(self, key, default=None):
        return {"storage_root_path": self.root, "storage_namespace": "data"}.get(key, default)


def test_report_storage_is_account_scoped(tmp_path):
    config = Config(tmp_path)
    saved = save_report(config, "alice", "a: 1\n", "yaml")
    path, mime = resolve_report(config, "alice", saved["file_id"])
    assert path.read_text() == "a: 1\n"
    assert mime == "application/yaml"
    assert ServeFileHandler(config).execute({"file_id": saved["file_id"]}, account_name="alice")["ok"]
    assert not ServeFileHandler(config).execute({"file_id": saved["file_id"]}, account_name="bob")["ok"]
    with pytest.raises(ValueError):
        resolve_report(config, "alice", "../../etc/passwd")
    with pytest.raises(ValueError):
        save_report(config, "../alice", "x", "json")


def test_report_result_generates_file_event_without_file_bytes():
    saved = {"file_id": "abc", "mime_type": "application/yaml", "download_name": "trace.yaml", "size_bytes": 100000}
    call = _ToolCall(call_id="c1", name="execution_trace", arguments_raw="{}")
    events = list(LLMLoopRunner._inspect_raw_results([(call, json.dumps({
        "ok": True, "tool": "execution_trace", "file": saved, "summary": {"tool_calls": 2}
    }))]))
    assert len(events) == 1
    assert events[0].type == "file"
    assert events[0].file_id == "abc"
    assert events[0].size_bytes == 100000
    assert "file_id" in events[0].to_sse()
