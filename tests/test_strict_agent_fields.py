"""Tests for strict_agent_fields toggle in Agent.from_dict() and AgentManager.

When strict=True (default), unknown fields raise ValueError.
When strict=False, unknown fields log a warning and are stripped.
"""

import json
import logging

from src.agent.agent import Agent
from src.agent.agent_manager import AgentManager


class TestAgentFromDictStrict:
    """Tests for Agent.from_dict strict parameter."""

    def test_unknown_field_raises_when_strict_true(self):
        """By default (strict=True), unknown fields raise ValueError."""
        try:
            Agent.from_dict({"name": "test", "unknown_field": "oops"})
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "unknown" in str(e).lower()
            assert "test" in str(e)

    def test_unknown_field_warns_when_strict_false(self, caplog):
        """When strict=False, unknown fields log a warning and are stripped."""
        caplog.set_level(logging.WARNING)
        agent = Agent.from_dict(
            {"name": "lenient", "extra_field": "value", "another_extra": 42},
            strict=False,
        )
        assert agent.name == "lenient"
        # Should have been constructed without error
        assert isinstance(agent, Agent)

        # Check that warnings were logged
        log_text = caplog.text.lower()
        assert "lenient" in log_text
        assert "unknown" in log_text
        assert "extra_field" in log_text
        assert "another_extra" in log_text

    def test_strict_false_removes_unknown_keys(self):
        """Unknown keys should not end up in the agent."""
        agent = Agent.from_dict(
            {"name": "clean", "metadata_tag": "should-be-removed"},
            strict=False,
        )
        # The unknown key should not be accessible as an attribute
        assert not hasattr(agent, "metadata_tag")

    def test_strict_false_still_validates_name(self):
        """Missing name still raises ValueError even when strict=False."""
        try:
            Agent.from_dict({"language_code": "en"}, strict=False)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "name" in str(e).lower()

    def test_strict_false_combined_with_legacy_keys(self):
        """Legacy keys are mapped before unknown key check, even with strict=False."""
        # 'select_type' is a legacy key that maps to 'context_type'
        agent = Agent.from_dict(
            {"name": "legacy", "select_type": "keyword", "x_custom": "ignored"},
            strict=False,
        )
        # Legacy key should have been mapped
        assert agent.context_type == "keyword"
        # Unknown key should have been stripped
        assert not hasattr(agent, "x_custom")


class TestAgentManagerStrictFields:
    """Tests for AgentManager strict_fields parameter."""

    def test_manager_defaults_to_strict(self, tmp_path):
        """AgentManager defaults to strict_fields=True."""
        agents = [
            {"name": "valid"},
            {"name": "bad", "unknown_key": "should fail"},
        ]
        data_file = tmp_path / "agents.json"
        data_file.write_text(json.dumps(agents), encoding="utf-8")

        manager = AgentManager(str(data_file))
        # Only valid agent loaded; bad one skipped
        assert manager.get_agent_names() == ["valid"]

    def test_manager_lenient_mode(self, tmp_path, caplog):
        """AgentManager with strict_fields=False loads agents with warnings."""
        caplog.set_level(logging.WARNING)
        agents = [
            {"name": "valid"},
            {"name": "extra", "unknown_key": "should warn not fail"},
        ]
        data_file = tmp_path / "agents.json"
        data_file.write_text(json.dumps(agents), encoding="utf-8")

        manager = AgentManager(str(data_file), strict_fields=False)
        # Both agents should load
        assert set(manager.get_agent_names()) == {"valid", "extra"}

        # Warning should be logged about unknown field
        log_text = caplog.text.lower()
        assert "extra" in log_text
        assert "unknown" in log_text

    def test_reload_with_changed_strict(self, tmp_path):
        """load_agents() can override the instance's strict_fields."""
        agents = [
            {"name": "test", "unknown_key": "val"},
        ]
        data_file = tmp_path / "agents.json"
        data_file.write_text(json.dumps(agents), encoding="utf-8")

        # Create with strict (default) — agent fails to load
        manager = AgentManager(str(data_file), strict_fields=True)
        assert manager.get_agent_names() == []

        # Reload with lenient — agent loads
        manager.load_agents(strict=False)
        assert manager.get_agent_names() == ["test"]

    def test_reload_respects_instance_strict_when_no_override(self, tmp_path):
        """When load_agents() is called without strict= arg, use instance default."""
        agents = [{"name": "ok", "extra": "data"}]
        data_file = tmp_path / "agents.json"
        data_file.write_text(json.dumps(agents), encoding="utf-8")

        manager = AgentManager(str(data_file), strict_fields=False)
        assert manager.get_agent_names() == ["ok"]

        # Reload without explicit strict — should keep lenient mode
        manager.load_agents()
        assert manager.get_agent_names() == ["ok"]
