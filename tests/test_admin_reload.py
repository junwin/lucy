"""Tests for POST /admin/reload endpoint logic.

Tests the underlying components (ConfigManager.reload, AgentManager.load_agents)
since importing the full Flask app requires the DI container which is not
available in unit tests.
"""

import json
import logging

import pytest

from src.config_manager import ConfigManager


# All test configs must include code_sandbox_path (absolute) to pass validation.
_BASE_CONFIG = {"code_sandbox_path": "/tmp/test_sandbox"}


class TestConfigManagerReload:
    """Tests for ConfigManager.reload() — the core of the reload endpoint."""

    def test_reload_returns_summary(self, tmp_path):
        """reload() returns a structured summary."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": 1, "b": 2}), encoding="utf-8"
        )

        mgr = ConfigManager(str(config_path))

        # Reload without changes
        summary = mgr.reload()
        assert summary["config_reloaded"] is True
        assert summary["keys_added"] == []
        assert summary["keys_removed"] == []
        assert summary["keys_changed"] == []

    def test_reload_detects_added_keys(self, tmp_path):
        """Keys added to the file are reported."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": 1}), encoding="utf-8"
        )

        mgr = ConfigManager(str(config_path))

        # Add keys
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": 1, "b": 2, "c": 3}), encoding="utf-8"
        )

        summary = mgr.reload()
        assert summary["config_reloaded"] is True
        assert sorted(summary["keys_added"]) == ["b", "c"]
        assert summary["keys_removed"] == []
        assert summary["keys_changed"] == []

    def test_reload_detects_removed_keys(self, tmp_path):
        """Keys removed from the file are reported."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": 1, "b": 2, "c": 3}), encoding="utf-8"
        )

        mgr = ConfigManager(str(config_path))

        # Remove keys
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": 1}), encoding="utf-8"
        )

        summary = mgr.reload()
        assert sorted(summary["keys_removed"]) == ["b", "c"]
        assert summary["keys_added"] == []
        assert summary["keys_changed"] == []

    def test_reload_detects_changed_keys(self, tmp_path):
        """Keys whose values changed are reported."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": "old", "b": "same"}), encoding="utf-8"
        )

        mgr = ConfigManager(str(config_path))

        # Change a value
        config_path.write_text(
            json.dumps({**_BASE_CONFIG, "a": "new", "b": "same"}), encoding="utf-8"
        )

        summary = mgr.reload()
        assert summary["keys_changed"] == ["a"]
        assert summary["keys_added"] == []
        assert summary["keys_removed"] == []

    def test_reload_invalid_json_keeps_old_state(self, tmp_path):
        """If the file becomes invalid JSON, old state preserved and error returned."""
        config_path = tmp_path / "config.json"
        original = {**_BASE_CONFIG, "key": "value"}
        config_path.write_text(json.dumps(original), encoding="utf-8")

        mgr = ConfigManager(str(config_path))
        assert mgr.get("key") == "value"

        # Corrupt the file
        config_path.write_text("not json {{{", encoding="utf-8")

        summary = mgr.reload()
        assert summary["config_reloaded"] is False
        assert "error" in summary

        # Old state preserved
        assert mgr.get("key") == "value"

    def test_reload_missing_file_keeps_old_state(self, tmp_path):
        """If the file is deleted, old state preserved and error returned."""
        config_path = tmp_path / "config.json"
        original = {**_BASE_CONFIG, "key": "value"}
        config_path.write_text(json.dumps(original), encoding="utf-8")

        mgr = ConfigManager(str(config_path))
        assert mgr.get("key") == "value"

        # Delete the file
        config_path.unlink()

        summary = mgr.reload()
        assert summary["config_reloaded"] is False
        assert "error" in summary

        # Old state preserved
        assert mgr.get("key") == "value"

    def test_reload_fails_on_bad_sandbox_path(self, tmp_path):
        """If the reloaded config fails sandbox validation, old state kept."""
        config_path = tmp_path / "config.json"
        original = {
            "code_sandbox_path": "/valid/absolute/path",
            "key_a": "value_a",
        }
        config_path.write_text(json.dumps(original), encoding="utf-8")

        mgr = ConfigManager(str(config_path))

        # Write invalid config: relative sandbox path
        bad = {
            "code_sandbox_path": "relative/path",
            "key_a": "value_a",
        }
        config_path.write_text(json.dumps(bad), encoding="utf-8")

        summary = mgr.reload()
        assert summary["config_reloaded"] is False
        assert "error" in summary

        # Old state preserved
        assert mgr.get("code_sandbox_path") == "/valid/absolute/path"

    def test_reload_with_strict_agent_fields_toggle(self, tmp_path):
        """ConfigManager can store and reload strict_agent_fields."""
        config_path = tmp_path / "config.json"
        original = {
            "code_sandbox_path": "/valid/absolute/path",
            "strict_agent_fields": True,
        }
        config_path.write_text(json.dumps(original), encoding="utf-8")

        mgr = ConfigManager(str(config_path))
        assert mgr.get("strict_agent_fields") is True

        # Toggle to False
        modified = {
            "code_sandbox_path": "/valid/absolute/path",
            "strict_agent_fields": False,
        }
        config_path.write_text(json.dumps(modified), encoding="utf-8")

        summary = mgr.reload()
        assert summary["config_reloaded"] is True
        assert "strict_agent_fields" in summary["keys_changed"]
        assert mgr.get("strict_agent_fields") is False


class TestAgentManagerReload:
    """Tests for AgentManager.load_agents() as used in the reload cycle."""

    def test_reload_with_strict_respects_parameter(self, tmp_path):
        """load_agents(strict=False) loads agents with unknown fields."""
        from src.agent.agent_manager import AgentManager

        agents = [
            {"name": "ok"},
            {"name": "has_extra", "bonus_field": "should warn"},
        ]
        agents_path = tmp_path / "agents.json"
        agents_path.write_text(json.dumps(agents), encoding="utf-8")

        mgr = AgentManager(str(agents_path), strict_fields=True)
        assert mgr.get_agent_names() == ["ok"]

        # Simulate reload with lenient mode
        mgr.load_agents(strict=False)
        assert set(mgr.get_agent_names()) == {"ok", "has_extra"}

    def test_reload_with_strict_enforcement(self, tmp_path, caplog):
        """load_agents(strict=True) rejects agents with unknown fields."""
        from src.agent.agent_manager import AgentManager

        caplog.set_level(logging.ERROR)

        agents = [
            {"name": "ok"},
            {"name": "bad", "typo_field": "oops"},
        ]
        agents_path = tmp_path / "agents.json"
        agents_path.write_text(json.dumps(agents), encoding="utf-8")

        # Start lenient — both load
        mgr = AgentManager(str(agents_path), strict_fields=False)
        assert set(mgr.get_agent_names()) == {"ok", "bad"}

        # Reload with strict — only 'ok' loads
        mgr.load_agents(strict=True)
        assert mgr.get_agent_names() == ["ok"]

    def test_reload_with_invalid_json_clears_agents(self, tmp_path):
        """If agents file becomes invalid JSON, agent list is cleared."""
        from src.agent.agent_manager import AgentManager

        agents = [{"name": "ok"}]
        agents_path = tmp_path / "agents.json"
        agents_path.write_text(json.dumps(agents), encoding="utf-8")

        mgr = AgentManager(str(agents_path))
        assert mgr.get_agent_names() == ["ok"]

        # Corrupt the file
        agents_path.write_text("not json {{{", encoding="utf-8")

        mgr.load_agents()
        assert mgr.get_agent_names() == []

    def test_reload_with_missing_file_clears_agents(self, tmp_path):
        """If agents file is deleted, agent list is cleared on reload."""
        from src.agent.agent_manager import AgentManager

        agents = [{"name": "ok"}]
        agents_path = tmp_path / "agents.json"
        agents_path.write_text(json.dumps(agents), encoding="utf-8")

        mgr = AgentManager(str(agents_path))
        assert mgr.get_agent_names() == ["ok"]

        # Delete the file
        agents_path.unlink()

        mgr.load_agents()
        assert mgr.get_agent_names() == []
