import pytest

from src.agent.agent import Agent


def test_agent_loads_with_provider_field():
    raw = {
        "name": "tester",
        "provider": "openai",
    }
    agent = Agent.from_dict(raw)
    assert agent.provider == "openai"


def test_agent_loads_without_provider_field_defaults_none():
    raw = {
        "name": "tester2",
    }
    agent = Agent.from_dict(raw)
    assert agent.provider is None


def test_to_dict_includes_provider_when_set():
    raw = {
        "name": "tester3",
        "provider": "mistral",
    }
    agent = Agent.from_dict(raw)
    d = agent.to_dict()
    assert "provider" in d
    assert d["provider"] == "mistral"


def test_typo_in_provider_passes_through():
    raw = {
        "name": "tester4",
        "provider": "oepnai",
    }
    agent = Agent.from_dict(raw)
    # No validation is performed at load time; the typo should be preserved
    assert agent.provider == "oepnai"
