import json
from types import SimpleNamespace

from src.config_manager import ConfigManager
from src.handlers.delegate_task_handler import DelegateTaskHandler


class FakeAgentManager:
    def __init__(self):
        self.agent = SimpleNamespace(
            name="nelly",
            default_context="lucyproject",
            model_requirements=lambda: object(),
        )

    def get_agent(self, name):
        return self.agent if name == self.agent.name else None

    def get_agent_names(self):
        return [self.agent.name]


def write_machines(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"code_sandbox_path": "/tmp"}))
    machines_file = tmp_path / "config.local.machines.json"
    machines_file.write_text(
        json.dumps(
            {
                "machines": {
                    "pi": {
                        "host": "pi.local",
                        "api_key": "shared",
                        "agents": ["nelly"],
                        "capabilities": ["development", "testing"],
                        "projects": {"lucy": "/srv/lucy"},
                        "model_sources": ["openai"],
                        "models": ["gpt-5.6-luna"],
                    },
                    "mint": {
                        "host": "mint.local",
                        "agents": ["colin"],
                        "capabilities": ["development"],
                        "model_sources": ["openai"],
                        "models": ["gpt-5-mini"],
                    },
                }
            }
        )
    )
    return SimpleNamespace(file_name=str(config_file))


def base_args(**changes):
    result = {
        "task": "Run the focused tests",
        "agentName": "nelly",
        "capabilities": ["development", "testing"],
        "project": "lucy",
        "machine": "",
        "contextName": "",
        "accountName": "",
        "timeout_seconds": 45,
    }
    result.update(changes)
    return result


def resolved_model(monkeypatch):
    monkeypatch.setattr(
        "src.handlers.delegate_task_handler.default_model_catalog.resolve",
        lambda requirements: SimpleNamespace(
            source="openai",
            model="gpt-5.6-luna",
        ),
    )


def test_selects_eligible_machine_and_reuses_remote_execute(monkeypatch, tmp_path):
    resolved_model(monkeypatch)
    config = write_machines(tmp_path)
    captured = {}

    def fake_execute(self, args, *, account_name="auto"):
        captured["args"] = args
        captured["account_name"] = account_name
        return {
            "ok": True,
            "tool": "remote_execute",
            "machine": args["machine"],
            "result": "green",
        }

    monkeypatch.setattr(
        "src.handlers.delegate_task_handler.RemoteExecuteHandler.execute",
        fake_execute,
    )

    handler = DelegateTaskHandler(config, FakeAgentManager())
    result = handler.execute(base_args(), account_name="junwin")

    assert result == {
        "ok": True,
        "tool": "delegate_task",
        "machine": "pi",
        "agent": "nelly",
        "source": "openai",
        "model": "gpt-5.6-luna",
        "result": "green",
    }
    assert captured["args"] == {
        "machine": "pi",
        "question": "Run the focused tests",
        "agentName": "nelly",
        "contextName": "lucyproject",
        "accountName": "",
        "timeout_seconds": 45,
    }
    assert captured["account_name"] == "junwin"


def test_unknown_agent_fails_before_machine_selection(tmp_path):
    handler = DelegateTaskHandler(write_machines(tmp_path), FakeAgentManager())

    result = handler.execute(base_args(agentName="missing"))

    assert result["ok"] is False
    assert "Unknown agent" in result["error"]
    assert "nelly" in result["error"]


def test_no_machine_matches_requirements(monkeypatch, tmp_path):
    resolved_model(monkeypatch)
    handler = DelegateTaskHandler(write_machines(tmp_path), FakeAgentManager())

    result = handler.execute(base_args(capabilities=["gpu"]))

    assert result["ok"] is False
    assert "No eligible machine" in result["error"]
    assert "capabilities=gpu" in result["error"]


def test_machine_override_must_be_eligible(monkeypatch, tmp_path):
    resolved_model(monkeypatch)
    handler = DelegateTaskHandler(write_machines(tmp_path), FakeAgentManager())

    result = handler.execute(base_args(machine="mint"))

    assert result["ok"] is False
    assert "machine=mint" in result["error"]


def test_invalid_capabilities_are_rejected(tmp_path):
    handler = DelegateTaskHandler(write_machines(tmp_path), FakeAgentManager())

    result = handler.execute(base_args(capabilities="development"))

    assert result["ok"] is False
    assert "capabilities must be a list" in result["error"]


def test_runtime_constructor_loads_agent_manager_from_config(tmp_path):
    agents_file = tmp_path / "agents.json"
    agents_file.write_text(json.dumps([{"name": "nelly"}]))
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "code_sandbox_path": "/tmp",
                "agents_path": str(agents_file),
            }
        )
    )

    handler = DelegateTaskHandler(ConfigManager(str(config_file)))

    assert handler.agent_manager.is_valid("nelly")
