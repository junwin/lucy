"""Regression tests for fcp_models (GH issue #132 crash site).

ProcessorContext.from_agent must tolerate context_name=None instead of
raising AttributeError: 'NoneType' object has no attribute 'strip'.
"""

from types import SimpleNamespace

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
