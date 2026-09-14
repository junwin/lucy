"""Regression tests for fcp_models (GH issue #132 crash site).

ProcessorContext.from_agent must tolerate context_name=None instead of
raising AttributeError: 'NoneType' object has no attribute 'strip'.
"""

from types import SimpleNamespace

from src.agent import Agent
from src.message_processors.fcp_models import ProcessorContext


def make_agent(default_context=None):
    return SimpleNamespace(
        name="test",
        default_context=default_context,
        max_function_call_iterations=5,
        provider=None,
        model="test-model",
        temperature=0.0,
        context_type="hybrid",
        save_responses=False,
        delegation_depth=0,
    )


def test_from_agent_with_none_context_name_uses_default_context():
    ctx = ProcessorContext.from_agent(
        primary_agent=make_agent(default_context="default-ctx"),
        account={"accountId": "acct"},
        conversation_id="conv-1",
        context_name=None,
    )
    assert ctx.context_name == "default-ctx"


def test_from_agent_with_none_context_name_and_no_default_is_empty():
    ctx = ProcessorContext.from_agent(
        primary_agent=make_agent(default_context=None),
        account={"accountId": "acct"},
        conversation_id="conv-1",
        context_name=None,
    )
    assert ctx.context_name == ""



def test_from_agent_resolves_model_policy_through_galet_catalog():
    agent = Agent.from_dict(
        {
            "name": "worker",
            "model": "gpt-5-mini",
            "model_policy": {
                "profile": "focused-development",
                "required_capabilities": ["tool-calling", "code-generation"],
                "preferred_model": "gpt-5-mini",
                "preferred_source": "openai",
            },
        }
    )

    ctx = ProcessorContext.from_agent(
        primary_agent=agent,
        account={"accountId": "acct"},
        conversation_id="conv-policy",
        context_name="",
    )

    assert ctx.model == "gpt-5-mini"
    assert ctx.provider == "openai"


def test_from_agent_preserves_legacy_model_without_policy():
    ctx = ProcessorContext.from_agent(
        primary_agent=make_agent(),
        account={"accountId": "acct"},
        conversation_id="conv-legacy",
        context_name="",
    )

    assert ctx.model == "test-model"
    assert ctx.provider is None
