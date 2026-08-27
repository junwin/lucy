from __future__ import annotations
import logging
from src.agent.agent import Agent


def test_allowed_tools_none_no_tools(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=None, save_responses=False)

    resp = proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    # ensure the LLM was called with no tools
    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == []


def test_allowed_tools_empty_no_tools(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=[], save_responses=False)

    resp = proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == []


def test_allowed_tools_subset_only_passed(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=["t2"], save_responses=False)

    resp = proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t2"}]


def test_allowed_tools_unknown_names_ignored_silently(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=["t2", "nope"], save_responses=False)

    proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    # Unknown allowed_tools entries are silently ignored (no warning, no error).
    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t2"}]


# ---------------------------------------------------------------------------
# resolve_tool_defs() — the shared tool-resolution helper (single source of
# truth used by process_message, process_message_streaming and the
# /prompt_builder/metrics endpoint).
# ---------------------------------------------------------------------------


def test_resolve_tool_defs_none_allows_no_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=None, save_responses=False)

    assert resolve_tool_defs(registry, agent) == []


def test_resolve_tool_defs_empty_allows_no_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=[], save_responses=False)

    assert resolve_tool_defs(registry, agent) == []


def test_resolve_tool_defs_subset_preserves_registry_order():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}])
    agent = Agent(name="a", allowed_tools=["t3", "t1"], save_responses=False)

    # Registry order wins, not allowed_tools order.
    result = resolve_tool_defs(registry, agent)
    assert [fd["name"] for fd in result] == ["t1", "t3"]


def test_resolve_tool_defs_unknown_names_ignored_and_logged(caplog):
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    caplog.set_level(logging.WARNING)
    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=["t2", "nope"], save_responses=False)

    result = resolve_tool_defs(registry, agent)

    assert [fd["name"] for fd in result] == ["t2"]
    found = False
    for rec in caplog.records:
        if "unknown allowed_tools entries" in rec.getMessage():
            found = True
            break
    assert found, "Expected warning about unknown allowed_tools entries"


def test_resolve_tool_defs_agent_without_allowed_tools_attribute():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    class BareAgent:
        pass

    registry = FakeRegistry(tool_defs=[{"name": "t1"}])
    assert resolve_tool_defs(registry, BareAgent()) == []


# ---------------------------------------------------------------------------
# Streaming path applies the same tool filtering as process_message.
# ---------------------------------------------------------------------------


def test_streaming_applies_allowed_tools_filter(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=["t2"], save_responses=False)

    list(proc.process_message_streaming(primary_agent=agent, account={"accountId": "acct"}, message="hi"))

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t2"}]


def test_streaming_allowed_tools_none_no_tools(make_proc, registry, llm_adapter):
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=None, save_responses=False)

    list(proc.process_message_streaming(primary_agent=agent, account={"accountId": "acct"}, message="hi"))

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == []


# ---------------------------------------------------------------------------
# Context tool handling.
#
# resolve_tool_defs() (the legacy helper, still used by the metrics endpoint)
# treats Context.extra['allowed_tools'] as a narrowing list clamped by
# agent.allowed_tools. The FCP's active pipeline (issue #126) does NOT read
# context allowed_tools at all -- only agent.allowed_tools is used; the
# context contributes required_tools instead.
# ---------------------------------------------------------------------------


def _make_context_state(data):
    from datetime import datetime, timezone
    from src.storage.models import Context

    return Context(
        id="ctx",
        account_name="acct",
        text=data.get("text", ""),
        extra={k: v for k, v in data.items() if k != "text"},
        updated_at=datetime.now(timezone.utc),
    )


def test_resolve_tool_defs_no_context_state_uses_agent_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}])
    agent = Agent(name="a", allowed_tools=["t1", "t3"], save_responses=False)

    result = resolve_tool_defs(registry, agent, context_state=None)
    assert [fd["name"] for fd in result] == ["t1", "t3"]


def test_resolve_tool_defs_context_without_tool_list_uses_agent_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=["t1", "t2"], save_responses=False)

    # Context is active but carries no 'allowed_tools' key -> agent list unchanged.
    result = resolve_tool_defs(registry, agent, context_state=_make_context_state({"text": "hi"}))
    assert [fd["name"] for fd in result] == ["t1", "t2"]


def test_resolve_tool_defs_context_list_narrows_agent_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}])
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    result = resolve_tool_defs(registry, agent, context_state=_make_context_state({"allowed_tools": ["t3", "t1"]}))
    # Registry order wins; only tools in both lists survive.
    assert [fd["name"] for fd in result] == ["t1", "t3"]


def test_resolve_tool_defs_context_list_exceeding_agent_permissions_clamped(caplog):
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    caplog.set_level(logging.WARNING)
    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}, {"name": "t3"}])
    agent = Agent(name="a", allowed_tools=["t1"], save_responses=False)

    result = resolve_tool_defs(
        registry,
        agent,
        context_state=_make_context_state({"allowed_tools": ["t1", "t2", "t3"]}),
    )
    # Context cannot grant tools the agent does not allow.
    assert [fd["name"] for fd in result] == ["t1"]

    found = False
    for rec in caplog.records:
        if "exceeds agent" in rec.getMessage() and "clamped" in rec.getMessage():
            found = True
            break
    assert found, "Expected warning about context tools clamped by agent allowed_tools"


def test_resolve_tool_defs_context_cannot_grant_when_agent_has_no_tools():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=None, save_responses=False)

    # Hard ceiling: no agent permission -> context list grants nothing.
    result = resolve_tool_defs(registry, agent, context_state=_make_context_state({"allowed_tools": ["t1"]}))
    assert result == []


def test_resolve_tool_defs_context_empty_list_does_not_restrict():
    from src.message_processors.function_calling_processor import resolve_tool_defs
    from tests.conftest import FakeRegistry

    registry = FakeRegistry(tool_defs=[{"name": "t1"}, {"name": "t2"}])
    agent = Agent(name="a", allowed_tools=["t1", "t2"], save_responses=False)

    result = resolve_tool_defs(registry, agent, context_state=_make_context_state({"allowed_tools": []}))
    assert [fd["name"] for fd in result] == ["t1", "t2"]


def test_process_message_ignores_context_allowed_tools(make_proc, registry, llm_adapter, prompt_builder):
    from datetime import datetime, timezone
    from src.storage.models import Context

    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]
    prompt_builder._get_context_state.return_value = Context(
        id="ctx",
        account_name="acct",
        extra={"allowed_tools": ["t2"]},
        updated_at=datetime.now(timezone.utc),
    )

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct"},
        message="hi",
        context_name="ctx",
    )

    # Context allowed_tools is ignored; only agent.allowed_tools is read.
    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]


def test_process_message_context_without_tool_list_uses_agent_tools(make_proc, registry, llm_adapter, prompt_builder):
    from datetime import datetime, timezone
    from src.storage.models import Context

    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}]
    prompt_builder._get_context_state.return_value = Context(
        id="ctx",
        account_name="acct",
        text="hi",
        updated_at=datetime.now(timezone.utc),
    )

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2"], save_responses=False)

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct"},
        message="hi",
        context_name="ctx",
    )

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t1"}, {"name": "t2"}]


def test_process_message_context_tool_list_clamped_by_agent_permissions(make_proc, registry, llm_adapter, prompt_builder):
    from datetime import datetime, timezone
    from src.storage.models import Context

    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]
    prompt_builder._get_context_state.return_value = Context(
        id="ctx",
        account_name="acct",
        extra={"allowed_tools": ["t1", "t2", "t3"]},
        updated_at=datetime.now(timezone.utc),
    )

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1"], save_responses=False)

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct"},
        message="hi",
        context_name="ctx",
    )

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t1"}]


def test_streaming_ignores_context_allowed_tools(make_proc, registry, llm_adapter, prompt_builder):
    from datetime import datetime, timezone
    from src.storage.models import Context

    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]
    prompt_builder._get_context_state.return_value = Context(
        id="ctx",
        account_name="acct",
        extra={"allowed_tools": ["t2"]},
        updated_at=datetime.now(timezone.utc),
    )

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    list(proc.process_message_streaming(
        primary_agent=agent,
        account={"accountId": "acct"},
        message="hi",
        context_name="ctx",
    ))

    # Context allowed_tools is ignored; only agent.allowed_tools is read.
    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}]


# ---------------------------------------------------------------------------
# Handler schema budget guardrail - max_handler_schema_tokens
#
# The FCP resolves the tool set via the tool-selection pipeline (issue #126),
# which RAISES ToolSelectionError('budget_exceeded') when the serialized
# schemas exceed the configured cap -- no silent trim. The legacy
# apply_handler_schema_budget() helper (still used by the metrics endpoint)
# retains the old trim-from-tail behaviour and is tested directly below.
# ---------------------------------------------------------------------------


def _big_tool_def(name: str, desc_len: int = 300) -> dict:
    """A tool def large enough that schema token estimates are meaningful."""
    return {
        "name": name,
        "description": "d" * desc_len,
        "parameters": {
            "type": "object",
            "properties": {"p": {"type": "string"}},
        },
    }


def _schema_tokens(function_defs) -> int:
    import json as _json

    from src.prompt_builders.prompt_builder import estimate_tokens_from_text

    return estimate_tokens_from_text(_json.dumps(function_defs, ensure_ascii=False))


def test_handler_schema_cap_over_budget_returns_error(make_proc, registry, llm_adapter, config):
    """Over the cap the pipeline raises and the FCP surfaces the error message."""
    defs = [_big_tool_def("t1"), _big_tool_def("t2"), _big_tool_def("t3")]
    registry._tool_defs = defs
    # Cap fits exactly two defs; the third exceeds the budget.
    config.values["max_handler_schema_tokens"] = _schema_tokens(defs[:2])

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    resp = proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi").text

    # The pipeline raises budget_exceeded; the FCP returns the human-readable
    # message and the main LLM is never called.
    assert "max_handler_schema_tokens" in resp
    llm_adapter.call_model.assert_not_called()


def test_handler_schema_cap_under_budget_no_trim_no_warning(make_proc, registry, llm_adapter, config, caplog):
    """Under the cap the tool set is passed through unchanged and no warning is logged."""
    caplog.set_level(logging.WARNING)
    defs = [_big_tool_def("t1"), _big_tool_def("t2"), _big_tool_def("t3")]
    registry._tool_defs = defs
    config.values["max_handler_schema_tokens"] = _schema_tokens(defs) * 10

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert [fd["name"] for fd in called_tools] == ["t1", "t2", "t3"]

    assert not any("handler schema tokens" in r.getMessage() for r in caplog.records)


def test_handler_schema_cap_zero_disables_guardrail(make_proc, registry, llm_adapter, config, caplog):
    """max_handler_schema_tokens <= 0 disables the guardrail entirely."""
    caplog.set_level(logging.WARNING)
    defs = [_big_tool_def("t1"), _big_tool_def("t2"), _big_tool_def("t3")]
    registry._tool_defs = defs
    config.values["max_handler_schema_tokens"] = 0

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert [fd["name"] for fd in called_tools] == ["t1", "t2", "t3"]
    assert not any("handler schema tokens" in r.getMessage() for r in caplog.records)


def test_handler_schema_budget_keeps_single_oversized_def():
    """A single def that alone exceeds the cap is kept (trim from tail, never to zero)."""
    from src.message_processors.function_calling_processor import apply_handler_schema_budget
    from tests.conftest import FakeConfig

    defs = [_big_tool_def("t1", desc_len=20000)]
    config = FakeConfig(values={"max_handler_schema_tokens": 100})

    result = apply_handler_schema_budget(defs, config, agent_name="a")

    assert [fd["name"] for fd in result] == ["t1"]


def test_streaming_handler_schema_cap_over_budget_emits_error(make_proc, registry, llm_adapter, config):
    """The streaming path emits an SSE 'error' event when the budget is exceeded."""
    defs = [_big_tool_def("t1"), _big_tool_def("t2"), _big_tool_def("t3")]
    registry._tool_defs = defs
    config.values["max_handler_schema_tokens"] = _schema_tokens(defs[:2])

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)
    agent = Agent(name="a", allowed_tools=["t1", "t2", "t3"], save_responses=False)

    events = list(proc.process_message_streaming(
        primary_agent=agent,
        account={"accountId": "acct"},
        message="hi",
    ))

    # budget_exceeded is surfaced as an SSE error event, not a silent trim.
    assert any('"type":"error"' in e and "max_handler_schema_tokens" in e for e in events)
    llm_adapter.call_model.assert_not_called()
