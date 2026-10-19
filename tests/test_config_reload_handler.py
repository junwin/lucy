"""Tests for the config_reload tool handler.

The handler is a thin wrapper over reload_config_and_agents(), which also backs
POST /admin/reload; these tests check the handler's own contract (shared
instances, status translation) rather than re-testing reload semantics.
"""

import json

import pytest

from src.agent.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.handlers.config_reload_handler import ConfigReloadHandler

# Config must carry an absolute code_sandbox_path to pass reload validation.
_BASE_CONFIG = {"code_sandbox_path": "/tmp/test_sandbox"}


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def runtime(tmp_path):
    """Live-ish ConfigManager and AgentManager sharing one agents file."""
    agents_path = tmp_path / "agents.json"
    _write_json(agents_path, [{"name": "alpha"}, {"name": "beta"}])

    config_path = tmp_path / "config.json"
    _write_json(
        config_path,
        {**_BASE_CONFIG, "agents_path": str(agents_path), "strict_agent_fields": True},
    )

    config = ConfigManager(str(config_path))
    manager = AgentManager(str(agents_path))
    return config, manager, config_path, agents_path


def test_reload_publishes_config_and_agents(runtime):
    config, manager, config_path, agents_path = runtime
    handler = ConfigReloadHandler(config)

    _write_json(agents_path, [{"name": "alpha"}, {"name": "gamma"}])
    _write_json(
        config_path,
        {**_BASE_CONFIG, "agents_path": str(agents_path), "strict_agent_fields": True, "new_key": 1},
    )

    result = handler.execute({}, config=config, agent_manager=manager)

    assert result["ok"] is True
    assert result["tool"] == "config_reload"
    assert result["config_reloaded"] is True
    assert result["keys_added"] == ["new_key"]
    assert result["agents_loaded"] == 2
    assert result["agents_added"] == ["gamma"]
    assert result["agents_removed"] == ["beta"]
    assert set(manager.get_agent_names()) == {"alpha", "gamma"}
    assert config.get("new_key") == 1


def test_failed_agent_reload_preserves_live_state(runtime):
    config, manager, config_path, agents_path = runtime
    handler = ConfigReloadHandler(config)
    before_config = dict(config.config)
    before_agents = manager.agents

    agents_path.write_text("{ not json", encoding="utf-8")

    result = handler.execute({}, config=config, agent_manager=manager)

    assert result["ok"] is False
    assert result["config_reloaded"] is False
    assert result["failed_stage"] == "agents"
    assert result["error"]["code"] == "reload_failed"
    assert config.config == before_config
    assert manager.agents is before_agents
    assert set(manager.get_agent_names()) == {"alpha", "beta"}


def test_failed_config_reload_preserves_live_state(runtime):
    config, manager, config_path, agents_path = runtime
    handler = ConfigReloadHandler(config)
    before_config = dict(config.config)

    _write_json(config_path, {"code_sandbox_path": "relative/path"})

    result = handler.execute({}, config=config, agent_manager=manager)

    assert result["ok"] is False
    assert result["failed_stage"] == "config"
    assert config.config == before_config


def test_missing_agent_manager_is_reported(runtime):
    config, _manager, _config_path, _agents_path = runtime
    handler = ConfigReloadHandler(config)

    result = handler.execute({}, config=config)

    assert result["ok"] is False
    assert result["error"]["code"] == "missing_agent_manager"


def test_plain_dict_config_is_rejected(runtime):
    _config, manager, _config_path, _agents_path = runtime
    handler = ConfigReloadHandler({"code_sandbox_path": "/tmp/test_sandbox"})

    result = handler.execute({}, agent_manager=manager)

    assert result["ok"] is False
    assert result["error"]["code"] == "config_manager_required"


def test_tool_definition_has_no_required_arguments():
    definition = ConfigReloadHandler.tool_def()

    assert definition["name"] == "config_reload"
    assert definition["parameters"]["required"] == []
    assert definition["parameters"]["properties"] == {}
