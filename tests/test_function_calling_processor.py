import pytest
from unittest.mock import Mock


def test_no_tool_calls_returns_text(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeAgent

    proc = make_proc()

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "hello!"

    out = proc.process_message(
        primary_agent=FakeAgent(save_responses=False),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "hello!"
    assert llm_adapter.call_model.call_count == 1


def test_tool_call_executes_handler_and_chains(make_proc, prompt_builder, llm_adapter, storage):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent, setup_tool_then_text

    handler = FakeHandler({"ok": True, "value": 123})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    proc = make_proc(registry=reg, storage=storage)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "do thing"}]

    setup_tool_then_text(
        llm_adapter,
        tool_name="my_tool",
        tool_args='{"x": 1}',
        final_text="done",
    )

    out = proc.process_message(
        primary_agent=FakeAgent(save_responses=False, max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="do thing",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "done"
    # handler.calls is [(args, account_name, context_dict)]
    assert len(handler.calls) == 1
    assert handler.calls[0][0] == {"x": 1}
    assert handler.calls[0][1] == "acct1"
    # context dict should contain expected keys (account_name is NOT in context dict)
    ctx = handler.calls[0][2]
    assert ctx["primary_agent"] is not None
    assert ctx["conversation_id"] == "c1"
    # account_name is passed as explicit kwarg, not in context dict
    assert "account_name" not in ctx

    first_call_kwargs = llm_adapter.call_model.call_args_list[0].kwargs
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs

    assert first_call_kwargs["previous_response_id"] is None
    assert second_call_kwargs["previous_response_id"] == "r1"
    assert second_call_kwargs["input"][0]["call_id"] == "call-1"


def test_tool_calls_without_response_id_raises(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent
    from src.message_processors.function_calling_processor import ToolHandlerError

    reg = FakeRegistry(
        handler_by_name={"t": FakeHandler({"ok": True})},
        tool_defs=[{"name": "t"}],
    )
    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = None
    llm_adapter.extract_tool_calls.return_value = [{"name": "t", "id": "c1", "arguments": "{}"}]

    with pytest.raises(ToolHandlerError):
        proc.process_message(
            primary_agent=FakeAgent(),
            account={"accountId": "acct1"},
            message="x",
            conversation_id="c1",
            context_name="ctx",
        )


def test_max_iterations_exceeded_returns_limit_message(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "loop"}]

    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]
    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{}",
    }

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=1),
        account={"accountId": "acct1"},
        message="loop",
        conversation_id="c1",
        context_name="ctx",
    )

    assert "internal limit" in out.lower()
    assert llm_adapter.call_model.call_count == 1


def test_bad_json_tool_args_falls_back_to_empty_dict(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent, setup_tool_then_text

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "bad json"}]

    setup_tool_then_text(
        llm_adapter,
        tool_name="my_tool",
        tool_args="{not-json",
        final_text="ok",
    )

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="bad json",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "ok"
    # handler.calls is [(args, account_name, context_dict)]
    assert len(handler.calls) == 1
    assert handler.calls[0][0] == {}
    assert handler.calls[0][1] == "acct1"
    ctx = handler.calls[0][2]
    assert ctx["conversation_id"] == "c1"




def test_handler_exception_is_wrapped_in_tool_handler_error(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent
    from src.message_processors.function_calling_processor import ToolHandlerError

    handler = FakeHandler(exc=RuntimeError("boom"))
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "explode"}]

    llm_adapter.call_model.return_value = object()
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [{"name": "my_tool", "id": "call-1", "arguments": "{}"}]

    with pytest.raises(ToolHandlerError):
        proc.process_message(
            primary_agent=FakeAgent(max_function_call_iterations=2),
            account={"accountId": "acct1"},
            message="explode",
            conversation_id="c1",
            context_name="ctx",
        )


def test_delegate_tasks_tasklist_executes_worker_tasks_and_returns_summary(make_proc, prompt_builder, llm_adapter):
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent, setup_tool_then_text

    delegate_tasks_result = {
        "ok": True,
        "tool": "delegate_tasks",
        "kind": "tasklist",
        "description": "Do two things",
        "tasks": [
            {"id": "task-1", "type": "task", "title": "First", "agent": "colin", "instruction": "Do first"},
            {"id": "task-2", "type": "task", "title": "Second", "agent": "colin", "instruction": "Do second"},
        ],
    }

    delegate_handler = FakeHandler(delegate_tasks_result)
    reg = FakeRegistry(handler_by_name={"delegate_tasks": delegate_handler}, tool_defs=[{"name": "delegate_tasks"}])

    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    setup_tool_then_text(llm_adapter, tool_name="delegate_tasks", tool_args='{"goal":"x"}', final_text="all done")

    # Patch worker execution deterministically
    real_process = proc.process_message

    def side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            return f"worker_result: {message[:20]}"
        return real_process(primary_agent=primary_agent, message=message, **kwargs)

    # Only needed for delegation tests: short-circuit worker execution without recursing
    proc.process_message = Mock(side_effect=side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=2),
        secondary_agent=FakeAgent(name="colin"),
        processor_factory=object(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "all done"

    # We short-circuit worker execution, so we don't assert internal worker call counts here.
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    assert second_call_kwargs["previous_response_id"] == "r1"
    assert "tasks" in second_call_kwargs["input"][0]["output"]


def test_duplicate_tool_calls_breaks_loop(make_proc, prompt_builder, llm_adapter):
    """When the model repeats the exact same tool call twice, the loop breaks."""
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent

    handler = FakeHandler({"ok": True, "result": "some data"})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "search for stuff"}]

    # Two identical tool calls in a row — same name, same arguments
    resp1, resp2 = object(), object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]
    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "my_tool", "id": "call-1", "arguments": '{"query": "foo"}'}],
        [{"name": "my_tool", "id": "call-2", "arguments": '{"query": "foo"}'}],
    ]
    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=10),
        account={"accountId": "acct1"},
        message="search for stuff",
        conversation_id="c1",
        context_name="ctx",
    )

    # Should break early with the duplicate-detection message, not hit max_iterations
    assert "repeating" in out.lower() or "loop" in out.lower()
    # Only 2 LLM calls (first tool call, then duplicate detected)
    assert llm_adapter.call_model.call_count == 2


def test_different_tool_calls_do_not_trigger_duplicate_detection(make_proc, prompt_builder, llm_adapter):
    """Different tool calls (different args) should proceed normally."""
    from tests.conftest import FakeHandler, FakeRegistry, FakeAgent

    handler = FakeHandler({"ok": True})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    proc = make_proc(registry=reg)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "do two things"}]

    # Three responses: tool call 1, tool call 2 (different args), then final text
    resp1, resp2, resp3 = object(), object(), object()
    llm_adapter.call_model.side_effect = [resp1, resp2, resp3]
    llm_adapter.get_response_id.side_effect = ["r1", "r2", "r3"]
    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "my_tool", "id": "call-1", "arguments": '{"query": "foo"}'}],
        [{"name": "my_tool", "id": "call-2", "arguments": '{"query": "bar"}'}],
        [],
    ]
    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }
    llm_adapter.get_text.return_value = "done"

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=10),
        account={"accountId": "acct1"},
        message="do two things",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "done"
    assert llm_adapter.call_model.call_count == 3
