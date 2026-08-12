"""Tests for the agents_manage tool handler."""

import json

import pytest

from src.agent import Agent
from src.agent.agent_manager import AgentManager
from src.handlers.agents_manage_handler import AgentsManageHandler


class FakeConfig:
    """Minimal config object with the .get() surface the handler uses."""

    def __init__(self, agents_path: str, strict: bool = True):
        self.values = {
            "agents_path": agents_path,
            "strict_agent_fields": strict,
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


def _write_agents(path, agents):
    path.write_text(json.dumps(agents), encoding="utf-8")


@pytest.fixture
def agents_path(tmp_path):
    p = tmp_path / "agents.json"
    _write_agents(p, [{"name": "alpha"}, {"name": "beta"}])
    return p


@pytest.fixture
def cfg(agents_path):
    return FakeConfig(str(agents_path))


@pytest.fixture
def handler(cfg):
    return AgentsManageHandler(cfg)


def test_list(handler):
    res = handler.execute({"action": "list"})
    assert res["ok"] is True
    assert res["count"] == 2
    assert set(res["agent_names"]) == {"alpha", "beta"}


def test_get(handler):
    res = handler.execute({"action": "get", "name": "alpha"})
    assert res["ok"] is True
    assert res["agent"]["name"] == "alpha"


def test_get_missing(handler):
    res = handler.execute({"action": "get", "name": "nope"})
    assert res["ok"] is False
    assert res["error"]["code"] == "not_found"


def test_get_requires_name(handler):
    res = handler.execute({"action": "get"})
    assert res["ok"] is False
    assert res["error"]["code"] == "missing_name"


def test_upsert_new_and_persist(handler, agents_path):
    res = handler.execute(
        {"action": "upsert", "agent": {"name": "gamma", "model": "gpt-5-mini"}}
    )
    assert res["ok"] is True
    assert res["agent"]["name"] == "gamma"
    assert res["agent"]["model"] == "gpt-5-mini"

    data = json.loads(agents_path.read_text(encoding="utf-8"))
    assert any(a["name"] == "gamma" for a in data)


def test_upsert_updates_existing(handler, agents_path):
    res = handler.execute(
        {"action": "upsert", "agent": {"name": "alpha", "model": "gpt-5.2"}}
    )
    assert res["ok"] is True
    assert res["agent"]["model"] == "gpt-5.2"

    data = json.loads(agents_path.read_text(encoding="utf-8"))
    alpha = next(a for a in data if a["name"] == "alpha")
    assert alpha["model"] == "gpt-5.2"


def test_upsert_rejects_unknown_field_when_strict(agents_path):
    strict_cfg = FakeConfig(str(agents_path), strict=True)
    h = AgentsManageHandler(strict_cfg)
    res = h.execute({"action": "upsert", "agent": {"name": "x", "bogus_field": 1}})
    assert res["ok"] is False
    assert res["error"]["code"] == "validation_error"


def test_upsert_requires_agent_dict(handler):
    res = handler.execute({"action": "upsert", "agent": "not-a-dict"})
    assert res["ok"] is False
    assert res["error"]["code"] == "invalid_agent"


def test_upsert_requires_name(handler):
    res = handler.execute({"action": "upsert", "agent": {"model": "gpt-5-mini"}})
    assert res["ok"] is False
    assert res["error"]["code"] == "missing_name"


def test_delete(handler, agents_path):
    res = handler.execute({"action": "delete", "name": "alpha"})
    assert res["ok"] is True
    assert res["removed"] is True

    data = json.loads(agents_path.read_text(encoding="utf-8"))
    assert all(a["name"] != "alpha" for a in data)


def test_delete_missing_is_idempotent(handler):
    res = handler.execute({"action": "delete", "name": "nope"})
    assert res["ok"] is True
    assert res["removed"] is False


def test_reload_picks_up_disk_changes(handler, agents_path):
    _write_agents(agents_path, [{"name": "alpha"}, {"name": "beta"}, {"name": "delta"}])
    res = handler.execute({"action": "reload"})
    assert res["ok"] is True
    assert res["count"] == 3
    assert set(res["agent_names"]) == {"alpha", "beta", "delta"}


def test_uses_shared_agent_manager_from_context(cfg):
    shared = AgentManager.__new__(AgentManager)  # bypass __init__ so we control state
    shared.path = None
    shared.agents = [Agent(name="memory_only")]

    h = AgentsManageHandler(cfg)
    res = h.execute({"action": "list"}, agent_manager=shared)
    assert res["ok"] is True
    assert res["agent_names"] == ["memory_only"]


def test_invalid_action(handler):
    res = handler.execute({"action": "explode"})
    assert res["ok"] is False
    assert res["error"]["code"] == "invalid_action"
