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


def test_allowed_tools_unknown_names_logged_and_ignored(make_proc, registry, llm_adapter, caplog):
    caplog.set_level(logging.WARNING)
    registry._tool_defs = [{"name": "t1"}, {"name": "t2"}]

    proc = make_proc(registry=registry, llm_adapter=llm_adapter)

    agent = Agent(name="a", allowed_tools=["t2", "nope"], save_responses=False)

    resp = proc.process_message(primary_agent=agent, account={"accountId": "acct"}, message="hi")

    # unknown 'nope' should produce a warning
    found = False
    for rec in caplog.records:
        if "unknown allowed_tools entries" in rec.getMessage():
            found = True
            break
    assert found, "Expected warning about unknown allowed_tools entries"

    called_tools = llm_adapter.call_model.call_args.kwargs.get("tools")
    assert called_tools == [{"name": "t2"}]
