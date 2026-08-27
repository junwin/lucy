"""Unit tests for /prompt_builder/metrics tool-resolution agreement with the FCP.

The metrics endpoint must report the exact same tool set the
FunctionCallingProcessor would send to the model — both go through the shared
resolve_tool_defs() helper (single source of truth).
"""

from __future__ import annotations

from unittest.mock import Mock

from src.handlers.handler_registry import HandlerRegistry
from src.http_endpoints.prompt_builder_metrics_endpoints import prompt_builder_metrics_impl
from src.message_processors.function_calling_processor import resolve_tool_defs
from src.prompt_builders.prompt_builder import PromptBuilder


def _make_deps(*, allowed_tools, tool_defs):
    agent = Mock()
    agent.allowed_tools = allowed_tools
    agent.context_type = "hybrid"

    agent_manager = Mock()
    agent_manager.is_valid.return_value = True
    agent_manager.get_agent.return_value = agent

    registry = Mock()
    registry.tools.return_value = tool_defs

    prompt_builder = Mock()
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
    prompt_builder._last_prompt_token_breakdown = {"total_without_handlers": 10}

    def _container_get(cls):
        if cls is PromptBuilder:
            return prompt_builder
        if cls is HandlerRegistry:
            return registry
        raise KeyError(cls)

    container = Mock()
    container.get.side_effect = _container_get

    return agent_manager, container


def _call_metrics(agent_manager, container, context_name=None):
    payload = {"query": "q", "agentName": "peace", "accountName": "junwin"}
    if context_name is not None:
        payload["contextName"] = context_name
    return prompt_builder_metrics_impl(
        agent_manager,
        None,
        container,
        None,
        payload,
    )


def test_metrics_tool_set_agrees_with_fcp_resolve_tool_defs():
    agent_manager, container = _make_deps(
        allowed_tools=["t3", "t1"],
        tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}],
    )

    result, status = _call_metrics(agent_manager, container)

    assert status == 200
    assert result["tool_count"] == 2
    reported = [h["name"] for h in result["handlers"]]
    assert reported == ["t1", "t3"]

    # Same input through the FCP helper must agree exactly.
    expected = [
        fd["name"]
        for fd in resolve_tool_defs(container.get(HandlerRegistry), agent_manager.get_agent("peace"))
    ]
    assert reported == expected


def test_metrics_tool_set_empty_when_allowed_tools_none():
    agent_manager, container = _make_deps(
        allowed_tools=None,
        tool_defs=[{"name": "t1"}, {"name": "t2"}],
    )

    result, status = _call_metrics(agent_manager, container)

    assert status == 200
    assert result["tool_count"] == 0
    assert result["handlers"] == []


def test_metrics_tool_set_ignores_unknown_allowed_tools():
    agent_manager, container = _make_deps(
        allowed_tools=["t2", "nope"],
        tool_defs=[{"name": "t1"}, {"name": "t2"}],
    )

    result, status = _call_metrics(agent_manager, container)

    assert status == 200
    assert result["tool_count"] == 1
    assert [h["name"] for h in result["handlers"]] == ["t2"]


def test_metrics_tool_set_applies_context_tool_list():
    from datetime import datetime, timezone
    from src.storage.models import Context

    agent_manager, container = _make_deps(
        allowed_tools=["t1", "t2", "t3"],
        tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}],
    )
    prompt_builder = container.get(PromptBuilder)
    prompt_builder._get_context_state.return_value = Context(
        id="ctx",
        account_name="junwin",
        extra={"allowed_tools": ["t2"]},
        updated_at=datetime.now(timezone.utc),
    )

    result, status = _call_metrics(agent_manager, container, context_name="ctx")

    assert status == 200
    assert result["tool_count"] == 1
    assert [h["name"] for h in result["handlers"]] == ["t2"]


def test_metrics_applies_handler_schema_cap():
    """The metrics endpoint reports the trimmed set and the effective cap."""
    from tests.conftest import FakeConfig

    agent_manager, container = _make_deps(
        allowed_tools=["t1", "t2", "t3"],
        tool_defs=[
            {"name": "t1", "description": "x" * 300},
            {"name": "t2", "description": "x" * 300},
            {"name": "t3", "description": "x" * 300},
        ],
    )

    result, status = prompt_builder_metrics_impl(
        agent_manager,
        None,
        container,
        FakeConfig(values={"max_handler_schema_tokens": 200}),
        {"query": "q", "agentName": "peace", "accountName": "junwin"},
    )

    assert status == 200
    # Three defs exceed the cap; the tail (t3) is trimmed, matching what the FCP sends.
    reported = [h["name"] for h in result["handlers"]]
    assert reported == ["t1", "t2"]
    assert result["handler_schema_cap"] == 200
