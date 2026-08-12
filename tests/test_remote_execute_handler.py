import json
import os
from types import SimpleNamespace

import pytest

from src.config_manager import ConfigManager
from src.handlers.remote_execute_handler import RemoteExecuteHandler


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def temp_config(tmp_path):
    # Minimal config.json that satisfies ConfigManager validation
    cfg = {"code_sandbox_path": "/tmp"}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(cfg))

    machines = {
        "machines": {
            "pi4": {
                "scheme": "http",
                "host": "127.0.0.1",
                "port": 5000,
                "api_key": "sekret",
                "session_id": "fixed-session-id-123",
                "default_agent": "peace",
                "default_context": "lucyproject",
            }
        }
    }
    machines_file = tmp_path / "config.local.machines.json"
    machines_file.write_text(json.dumps(machines))

    return str(config_file)


def test_happy_path_sse(monkeypatch, temp_config):
    cfg = ConfigManager(temp_config)
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        captured["headers"] = headers
        # SSE stream with a final message event
        sse = (
            'data: {"kind":"message","content":"hello from remote"}\n\n'
            'data: {"kind":"done"}\n\n'
        )
        return FakeResponse(sse, status_code=200)

    monkeypatch.setattr("requests.post", fake_post)

    h = RemoteExecuteHandler(cfg)
    res = h.execute({"machine": "pi4", "question": "what's up"}, account_name="junwin")

    assert res["ok"] is True
    assert res["result"] == "hello from remote"
    assert captured["url"].startswith("http://127.0.0.1:5000/ask")
    assert captured["body"]["sessionId"] == "fixed-session-id-123"


def test_unknown_machine_lists_available(temp_config):
    cfg = ConfigManager(temp_config)
    h = RemoteExecuteHandler(cfg)
    res = h.execute({"machine": "unknown", "question": "hi"}, account_name="junwin")

    assert res["ok"] is False
    assert "Unknown machine" in res.get("error", "")
    # available machines should include 'pi4'
    assert "pi4" in res.get("error", "")


def test_session_id_reused_from_config(monkeypatch, temp_config):
    cfg = ConfigManager(temp_config)
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["body"] = json
        return FakeResponse('{"response":"ok"}', status_code=200)

    monkeypatch.setattr("requests.post", fake_post)

    h = RemoteExecuteHandler(cfg)
    res = h.execute({"machine": "pi4", "question": "ping"}, account_name="junwin")

    assert res["ok"] is True
    assert captured["body"]["sessionId"] == "fixed-session-id-123"
    # ensure the accountName fallback used the provided account
    assert captured["body"]["accountName"] == "junwin"
