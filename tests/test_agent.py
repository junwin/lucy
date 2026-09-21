import pytest

from src.agent.agent import Agent, ModelPolicy

CAP_FIELDS = (
    "max_tool_result_chars",
    "max_handler_schema_tokens",
    "context_text_soft_max_tokens",
    "prompt_budget_max_tokens",
)


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


def test_agent_cap_fields_default_to_none():
    """Absent override fields default to None (fall through to config)."""
    agent = Agent.from_dict({"name": "plain"})
    for field in CAP_FIELDS:
        assert getattr(agent, field) is None


def test_agent_from_dict_accepts_and_coerces_cap_fields():
    """The four cap keys are accepted and string values are coerced to int."""
    raw = {
        "name": "capped",
        "max_tool_result_chars": "5000",
        "max_handler_schema_tokens": 8000,
        "context_text_soft_max_tokens": "1500",
        "prompt_budget_max_tokens": 12000,
    }
    agent = Agent.from_dict(raw)
    assert agent.max_tool_result_chars == 5000
    assert agent.max_handler_schema_tokens == 8000
    assert agent.context_text_soft_max_tokens == 1500
    assert agent.prompt_budget_max_tokens == 12000


def test_agent_from_dict_accepts_zero_cap_fields():
    """0 is allowed at load time; non-positive semantics are a resolver concern."""
    agent = Agent.from_dict({"name": "zeroed", "max_tool_result_chars": 0})
    assert agent.max_tool_result_chars == 0


def test_agent_from_dict_rejects_negative_cap_fields():
    for field in CAP_FIELDS:
        with pytest.raises(ValueError, match="non-negative"):
            Agent.from_dict({"name": "bad", field: -1})


def test_agent_from_dict_rejects_non_numeric_cap_fields():
    with pytest.raises(ValueError, match="expected int"):
        Agent.from_dict({"name": "bad", "max_tool_result_chars": "many"})
    with pytest.raises(ValueError, match="expected int"):
        Agent.from_dict({"name": "bad", "max_handler_schema_tokens": [1, 2]})


def test_to_dict_emits_cap_fields_only_when_set_and_round_trips():
    values = {
        "max_tool_result_chars": 1000,
        "max_handler_schema_tokens": 2000,
        "context_text_soft_max_tokens": 3000,
        "prompt_budget_max_tokens": 4000,
    }
    agent = Agent.from_dict(dict({"name": "round"}, **values))
    dumped = agent.to_dict()
    for field, value in values.items():
        assert dumped[field] == value

    plain = Agent.from_dict({"name": "plain"})
    plain_dumped = plain.to_dict()
    for field in CAP_FIELDS:
        assert field not in plain_dumped

    restored = Agent.from_dict(dumped)
    for field, value in values.items():
        assert getattr(restored, field) == value

    restored_plain = Agent.from_dict(plain_dumped)
    for field in CAP_FIELDS:
        assert getattr(restored_plain, field) is None



def test_agent_loads_model_policy_and_builds_galet_requirements():
    agent = Agent.from_dict(
        {
            "name": "architect",
            "model": "legacy-model",
            "model_policy": {
                "profile": "reasoning",
                "required_capabilities": ["tool-calling", "structured-output"],
                "preferred_model": "gpt-5.6-sol",
                "preferred_source": "openai",
                "allow_fallback": True,
            },
        }
    )

    assert isinstance(agent.model_policy, ModelPolicy)
    requirements = agent.model_requirements()
    assert requirements.profile == "reasoning"
    assert requirements.required_capabilities == frozenset(
        {"tool-calling", "structured-output"}
    )
    assert requirements.preferred_model == "gpt-5.6-sol"
    assert requirements.preferred_source == "openai"
    assert requirements.allow_fallback is True


def test_model_policy_round_trips():
    agent = Agent.from_dict(
        {
            "name": "worker",
            "model_policy": {
                "profile": "focused-development",
                "required_capabilities": ["code-generation"],
                "preferred_model": "gpt-5-mini",
                "allow_fallback": False,
            },
        }
    )

    restored = Agent.from_dict(agent.to_dict())

    assert restored.model_policy == agent.model_policy


def test_legacy_agent_builds_fixed_model_requirements():
    agent = Agent.from_dict(
        {
            "name": "legacy",
            "model": "gpt-4o",
            "provider": "openai",
        }
    )

    requirements = agent.model_requirements()

    assert requirements.preferred_model == "gpt-4o"
    assert requirements.preferred_source == "openai"
    assert requirements.allow_fallback is False


@pytest.mark.parametrize(
    ("policy", "message"),
    [
        ("reasoning", "must be an object"),
        ({"unknown": True}, "unknown fields"),
        ({"required_capabilities": "tools"}, "must be a list"),
        ({"required_capabilities": [""]}, "non-empty strings"),
        ({"allow_fallback": "yes"}, "must be a bool"),
    ],
)
def test_invalid_model_policy_is_rejected(policy, message):
    with pytest.raises(ValueError, match=message):
        Agent.from_dict({"name": "invalid", "model_policy": policy})


def test_tool_discovery_defaults_enabled_and_round_trips() -> None:
    agent = Agent.from_dict({"name": "default-discovery"})

    assert agent.tool_discovery_enabled is True
    assert Agent.from_dict(agent.to_dict()).tool_discovery_enabled is True


def test_tool_discovery_can_be_disabled_and_coerces_boolean_strings() -> None:
    agent = Agent.from_dict(
        {
            "name": "no-discovery",
            "tool_discovery_enabled": "false",
        }
    )

    assert agent.tool_discovery_enabled is False
    dumped = agent.to_dict()
    assert dumped["tool_discovery_enabled"] is False
    assert Agent.from_dict(dumped).tool_discovery_enabled is False
