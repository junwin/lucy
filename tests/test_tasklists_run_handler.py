"""Tests for TasklistsRunHandler."""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import Mock

import pytest

from src.handlers.tasklists_run_handler import TasklistsRunHandler


class SimpleConfig:
    def __init__(self):
        self._m = {}

    def get(self, k, default=None):
        return self._m.get(k, default)


class FakeAutomationProcessor:
    """Minimal fake that records calls and returns a canned result."""

    def __init__(self, result: str = "ok", exc: Optional[Exception] = None):
        self.result = result
        self.exc = exc
        self.calls: list[dict] = []

    def execute_tasklist(self, **kwargs) -> str:
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.result


class FakeProcessorFactory:
    """Fake that returns a FakeAutomationProcessor."""

    def __init__(self, ap: Optional[FakeAutomationProcessor] = None):
        self.ap = ap or FakeAutomationProcessor()

    def get(self, name: str):
        if name == "automation_processor":
            return self.ap
        raise ValueError(f"Unknown processor: {name}")


def make_context(*, automation_processor=None, **overrides) -> Dict[str, Any]:
    ctx = {
        "primary_agent": Mock(name="lucy"),
        "account": {"accountId": "acct1"},
        "conversation_id": "conv-1",
        "context_name": "ctx1",
        "storage": Mock(),
        "registry": Mock(),
        "prompt_builder": Mock(),
        "config": SimpleConfig(),
        "chat2_store": None,
        "llm_adapter": None,
    }
    if automation_processor is not None:
        ctx["automation_processor"] = automation_processor
    ctx.update(overrides)
    return ctx


class TestTasklistsRunHandler:
    def test_tool_def_structure(self):
        """tool_def returns a valid OpenAI function definition."""
        td = TasklistsRunHandler.tool_def()
        assert td["type"] == "function"
        assert td["name"] == "tasklists_run"
        assert "tasklist_id" in td["parameters"]["properties"]
        assert "mode" in td["parameters"]["properties"]
        assert td["parameters"]["required"] == ["tasklist_id", "mode"]

    def test_result_schema_structure(self):
        """result_schema returns a valid JSON schema."""
        rs = TasklistsRunHandler.result_schema()
        assert rs["type"] == "object"
        assert "ok" in rs["properties"]
        assert "tool" in rs["properties"]

    def test_missing_tasklist_id_returns_error(self):
        """Empty or missing tasklist_id returns an error."""
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=FakeAutomationProcessor())

        result = handler.execute({}, account_name="alice", **ctx)
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_tasklist_id"

        result = handler.execute({"tasklist_id": ""}, account_name="alice", **ctx)
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_tasklist_id"

    def test_invalid_mode_returns_error(self):
        """Invalid mode returns an error."""
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=FakeAutomationProcessor())

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "invalid"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_mode"

    def test_missing_primary_agent_returns_error(self):
        """Missing primary_agent in context returns an error."""
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=FakeAutomationProcessor())
        del ctx["primary_agent"]

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_context"

    def test_missing_account_returns_error(self):
        """Missing account in context returns an error."""
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=FakeAutomationProcessor())
        del ctx["account"]

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_context"

    def test_missing_automation_processor_falls_back_to_processor_factory(self):
        """When automation_processor is not in context, handler uses processor_factory."""
        fake_ap = FakeAutomationProcessor(result="[AutomationProcessor] mode=single-step state=completed task='T1' executed=1")
        factory = FakeProcessorFactory(ap=fake_ap)
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=None, processor_factory=factory)

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is True
        assert result["tool"] == "tasklists_run"
        assert result["tasklist_id"] == "tl1"
        assert result["mode"] == "single-step"
        assert "completed" in result["result"]

        # Verify the automation processor was called with correct params
        assert len(fake_ap.calls) == 1
        call_kwargs = fake_ap.calls[0]
        assert call_kwargs["tasklist_id"] == "tl1"
        assert call_kwargs["mode"] == "single-step"
        assert call_kwargs["account_name"] == "alice"
        assert call_kwargs["conversation_id"] == "conv-1"

    def test_missing_automation_processor_and_no_factory_returns_error(self):
        """When both automation_processor and processor_factory are missing, returns error."""
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=None)
        # Remove processor_factory too (it's not in make_context by default)

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_dependency"

    def test_successful_single_step_execution(self):
        """Single-step execution returns ok with result."""
        fake_ap = FakeAutomationProcessor(result="[AutomationProcessor] mode=single-step state=completed task='T1' executed=1")
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=fake_ap)

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is True
        assert result["tool"] == "tasklists_run"
        assert result["tasklist_id"] == "tl1"
        assert result["mode"] == "single-step"
        assert "completed" in result["result"]

        # Verify the automation processor was called with correct params
        assert len(fake_ap.calls) == 1
        call_kwargs = fake_ap.calls[0]
        assert call_kwargs["tasklist_id"] == "tl1"
        assert call_kwargs["mode"] == "single-step"
        assert call_kwargs["account_name"] == "alice"
        assert call_kwargs["conversation_id"] == "conv-1"

    def test_successful_multi_step_execution(self):
        """Multi-step execution returns ok with result."""
        fake_ap = FakeAutomationProcessor(result="[AutomationProcessor] mode=multi-step state=completed task='T2' executed=3")
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=fake_ap)

        result = handler.execute(
            {"tasklist_id": "tl2", "mode": "multi-step"},
            account_name="bob",
            **ctx,
        )
        assert result["ok"] is True
        assert result["tasklist_id"] == "tl2"
        assert result["mode"] == "multi-step"
        assert "executed=3" in result["result"]

        assert len(fake_ap.calls) == 1
        assert fake_ap.calls[0]["mode"] == "multi-step"

    def test_execution_exception_returns_error(self):
        """When execute_tasklist raises, handler returns error."""
        fake_ap = FakeAutomationProcessor(exc=RuntimeError("something went wrong"))
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=fake_ap)

        result = handler.execute(
            {"tasklist_id": "tl1", "mode": "single-step"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "execution_failed"
        assert "something went wrong" in result["error"]["message"]

    def test_default_mode_is_single_step(self):
        """When mode is not provided, defaults to single-step."""
        fake_ap = FakeAutomationProcessor()
        handler = TasklistsRunHandler(SimpleConfig())
        ctx = make_context(automation_processor=fake_ap)

        result = handler.execute(
            {"tasklist_id": "tl1"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is True
        assert result["mode"] == "single-step"
        assert fake_ap.calls[0]["mode"] == "single-step"

    def test_agent_name_extracted_from_primary_agent(self):
        """Agent name is extracted from primary_agent.name."""
        fake_ap = FakeAutomationProcessor()
        handler = TasklistsRunHandler(SimpleConfig())

        mock_agent = Mock(name="lucy")
        mock_agent.name = "lucy"
        ctx = make_context(automation_processor=fake_ap, primary_agent=mock_agent)

        result = handler.execute(
            {"tasklist_id": "tl1"},
            account_name="alice",
            **ctx,
        )
        assert result["ok"] is True
        assert fake_ap.calls[0]["agent_name"] == "lucy"
