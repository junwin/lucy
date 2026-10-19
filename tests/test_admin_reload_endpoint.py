"""Exercise the real reload route and authentication without composing LLM services."""
import ast
import copy
import json
import logging
from pathlib import Path

from flask import Flask, jsonify, request
import pytest

from src.agent import AgentManager
from src.api_key import validate_api_key
from src.config_manager import ConfigManager
from src.http_endpoints.admin_reload import reload_config_and_agents

KEY = {"X-API-Key": "old-key"}


@pytest.fixture
def runtime(tmp_path):
    agents_file = tmp_path / "agents.json"
    agents_file.write_text(json.dumps([{"name": "old"}]))
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "code_sandbox_path": str(tmp_path), "agents_path": str(agents_file),
        "api_key_enabled": True, "api_key": "old-key",
    }))
    config = ConfigManager(str(config_file))
    manager = AgentManager(str(agents_file))
    app = Flask(__name__)
    namespace = dict(app=app, request=request, jsonify=jsonify, logging=logging,
                     config=config, agent_manager=manager, validate_api_key=validate_api_key,
                     reload_config_and_agents=reload_config_and_agents)
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    names = {"_check_api_key", "_enforce_api_key", "admin_reload"}
    routes = ast.Module(body=[node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    exec(compile(routes, "app.py", "exec"), namespace)
    app.config["TESTING"] = True
    return app.test_client(), config, manager, config_file, agents_file


def test_reload_updates_path_strictness_summary_and_next_request_key(runtime, tmp_path):
    client, config, manager, config_file, _ = runtime
    identity = config.config
    new_path = tmp_path / "new-agents.json"
    new_path.write_text(json.dumps([{"name": "new", "notes": "metadata"}]))
    candidate = {**config.config, "agents_path": str(new_path), "strict_agent_fields": False,
                 "api_key": "new-key"}
    config_file.write_text(json.dumps(candidate))
    response = client.post("/admin/reload", headers=KEY)
    assert response.status_code == 200
    body = response.get_json()
    assert body["agents_loaded"] == 1
    assert body["agent_names"] == body["agents_added"] == ["new"]
    assert body["agents_removed"] == ["old"]
    assert body["keys_added"] == ["strict_agent_fields"]
    assert body["keys_changed"] == ["agents_path", "api_key"]
    assert config.config is identity
    assert manager.path == new_path
    assert manager.strict_fields is False
    manager.reload_agents()  # Subsequent reloads keep the new path and policy.
    assert manager.get_agent_names() == ["new"]
    assert client.post("/admin/reload", headers=KEY).status_code == 401
    assert client.post("/admin/reload", headers={"X-API-Key": "new-key"}).status_code == 200


@pytest.mark.parametrize("failure,stage", [
    ("config_json", "config"), ("config_missing", "config"),
    ("config_shape", "config"), ("local_json", "config"), ("local_shape", "config"),
    ("sandbox", "config"), ("strict_type", "config"),
    ("agents_json", "agents"), ("agents_missing", "agents"),
    ("agents_shape", "agents"), ("agent_invalid", "agents"),
    ("unknown_field", "agents"), ("duplicate", "agents"), ("new_path_missing", "agents"),
])
def test_reload_failure_preserves_both_managers(runtime, failure, stage):
    client, config, manager, config_file, agents_file = runtime
    identity = config.config
    before = copy.deepcopy(identity)
    agents_before = manager.agents
    candidate = {**before, "api_key": "new-key"}
    config_file.write_text(json.dumps(candidate))
    local_file = config_file.with_name("config.local.json")
    if failure == "config_json":
        config_file.write_text("{")
    elif failure == "config_missing":
        config_file.unlink()
    elif failure == "config_shape":
        config_file.write_text("[]")
    elif failure.startswith("local_"):
        local_file.write_text("{" if failure == "local_json" else "[]")
    elif failure in {"sandbox", "strict_type", "new_path_missing"}:
        key, value = {"sandbox": ("code_sandbox_path", "relative"),
                      "strict_type": ("strict_agent_fields", "false"),
                      "new_path_missing": ("agents_path", str(agents_file) + ".missing")}[failure]
        config_file.write_text(json.dumps({**candidate, key: value}))
    elif failure == "agents_missing":
        agents_file.unlink()
    else:
        agents_file.write_text({
            "agents_json": "{", "agents_shape": "42",
            "agent_invalid": '[{"name":"valid"}, {}]',
            "unknown_field": '[{"name":"valid"}, {"name":"typo", "allowed_toolz":[]}]',
            "duplicate": '[{"name":"same"}, {"name":"same"}]',
        }[failure])
    response = client.post("/admin/reload", headers=KEY)
    assert response.status_code == 500
    assert response.get_json()["failed_stage"] == stage
    assert response.get_json()["config_reloaded"] is False
    assert config.config is identity
    assert config.config == before
    assert manager.agents is agents_before
    assert manager.get_agent_names() == ["old"]
    assert manager.path == agents_file
    assert manager.strict_fields is True
    assert client.post("/admin/reload", headers={"X-API-Key": "new-key"}).status_code == 401


def test_reload_applies_local_overrides(runtime):
    client, config, manager, config_file, agents_file = runtime
    config_file.with_name("config.local.json").write_text(json.dumps({"strict_agent_fields": False}))
    agents_file.write_text('[{"name":"new", "notes":"extra"}]')
    assert client.post("/admin/reload", headers=KEY).status_code == 200
    assert config.get("strict_agent_fields") is False
    assert manager.get_agent_names() == ["new"]


def test_reload_updates_existing_agent_prompt_and_tool_permissions(runtime):
    client, _, manager, _, agents_file = runtime
    agents_file.write_text(json.dumps([{
        "name": "old", "system_prompt": "Updated prompt", "allowed_tools": ["file_load"],
    }]))
    response = client.post("/admin/reload", headers=KEY)
    assert response.status_code == 200
    assert response.get_json()["agents_added"] == []
    assert response.get_json()["agents_removed"] == []
    agent = manager.get_agent("old")
    assert agent.system_prompt == "Updated prompt"
    assert agent.allows_tool("file_load")
    assert not agent.allows_tool("execute_command")


def test_reload_requires_authentication_before_any_mutation(runtime):
    client, config, manager, config_file, agents_file = runtime
    agents_file.write_text('[{"name":"new"}]')
    assert client.post("/admin/reload").status_code == 401
    assert manager.get_agent_names() == ["old"]
    assert client.get("/admin/reload", headers=KEY).status_code == 405


def test_empty_agents_list_is_an_explicit_valid_removal(runtime):
    client, _, manager, _, agents_file = runtime
    agents_file.write_text("[]")
    response = client.post("/admin/reload", headers=KEY)
    assert response.status_code == 200
    assert response.get_json()["agents_removed"] == ["old"]
    assert manager.get_agent_names() == []
