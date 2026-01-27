import json
import logging

from src.agent.agent_manager import AgentManager


def test_agent_manager_skips_unknown_field_agent(tmp_path, caplog):
    """One bad agent should not prevent other agents from loading.

    The bad agent has an unknown field, which should hard-fail Agent.from_dict,
    and AgentManager should log the exception at ERROR and continue.
    """

    caplog.set_level(logging.ERROR)

    agents = [
        {"name": "valid_agent", "language_code": "en-US"},
        {"name": "invalid_agent", "language_code": "en-US", "unknown_field": "oops"},
    ]

    data_file = tmp_path / "agents.json"
    data_file.write_text(json.dumps(agents), encoding="utf-8")

    manager = AgentManager(str(data_file))

    # Only the valid agent should be loaded
    assert manager.get_agent_names() == ["valid_agent"]

    # The logs should contain an error about the unknown field and mention the agent name
    log_text = caplog.text.lower()
    assert "invalid_agent" in log_text
    assert "unknown" in log_text
