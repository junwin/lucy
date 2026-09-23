"""Regression guards for prompt-builder endpoint interface resolution.

sqlite-vec implementation/retrieval coverage now lives in galet-memory. Lucy
keeps only the endpoint regression that verifies the PromptBuilderInterface is
requested and failures surface loudly.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.http_endpoints.prompt_builder_endpoints import build_prompt_impl
from src.http_endpoints.prompt_builder_metrics_endpoints import prompt_builder_metrics_impl
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface


def _agent_manager() -> Mock:
    agent = Mock()
    agent.context_type = "hybrid"
    agent_manager = Mock()
    agent_manager.is_valid.return_value = True
    agent_manager.get_agent.return_value = agent
    return agent_manager


@pytest.mark.unit
def test_prompt_builder_endpoints_resolve_interface_and_fail_loud() -> None:
    agent_manager = _agent_manager()
    requested: list = []

    def raising_get(cls):
        requested.append(cls)
        raise KeyError(cls)

    container = Mock()
    container.get.side_effect = raising_get

    payload = {
        "query": "q",
        "agentName": "peace",
        "accountName": "junwin",
        "contextType": "hybrid",
    }
    for impl in (build_prompt_impl, prompt_builder_metrics_impl):
        result, status = impl(agent_manager, None, container, None, payload)
        assert status == 500
        assert isinstance(result, dict)
        assert "error" in result

    assert PromptBuilderInterface in requested
