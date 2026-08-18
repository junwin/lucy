import pytest
from unittest.mock import Mock, patch


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


# ---------------------------------------------------------------------------
# _ensure_chat2_session context_name passthrough tests
# ---------------------------------------------------------------------------


class TestEnsureChat2SessionContextName:
    """Verify context_name flows through _ensure_chat2_session → create_session."""

    def test_context_name_passed_to_create_session(self, make_proc, prompt_builder, llm_adapter):
        """When a new session is created, context_name is passed through."""
        from tests.conftest import FakeAgent

        mock_store = Mock()
        mock_store.session_exists.return_value = False
        mock_store.create_session.return_value = Mock()
        mock_store.add_events.return_value = []

        proc = make_proc()
        proc.chat2_store = mock_store

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="lucyproject",
        )

        mock_store.create_session.assert_called_once()
        call_kwargs = mock_store.create_session.call_args.kwargs
        assert call_kwargs["context_name"] == "lucyproject"
        assert call_kwargs["friendly_name"] == "lucyproject"
        assert call_kwargs["session_id"] == "c1"
        assert call_kwargs["account_name"] == "acct1"

    def test_empty_context_name_becomes_none(self, make_proc, prompt_builder, llm_adapter):
        """Empty string context_name is normalized to None."""
        from tests.conftest import FakeAgent

        mock_store = Mock()
        mock_store.session_exists.return_value = False
        mock_store.create_session.return_value = Mock()
        mock_store.add_events.return_value = []

        proc = make_proc()
        proc.chat2_store = mock_store

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="",
        )

        mock_store.create_session.assert_called_once()
        call_kwargs = mock_store.create_session.call_args.kwargs
        assert call_kwargs["context_name"] is None
        assert call_kwargs["friendly_name"] is None

    def test_session_already_exists_skips_create(self, make_proc, prompt_builder, llm_adapter):
        """When the session already exists, create_session is NOT called."""
        from tests.conftest import FakeAgent

        mock_store = Mock()
        mock_store.session_exists.return_value = True
        mock_store.add_events.return_value = []

        proc = make_proc()
        proc.chat2_store = mock_store

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="already_exists_context",
        )

        mock_store.create_session.assert_not_called()
        # Events should still be written
        mock_store.add_events.assert_called_once()

    def test_no_chat2_store_no_crash(self, make_proc, prompt_builder, llm_adapter):
        """When chat2_store is None, process_message still works fine."""
        from tests.conftest import FakeAgent

        proc = make_proc()
        proc.chat2_store = None  # explicitly None

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "all good"

        out = proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="unused",
        )

        assert out == "all good"

    def test_save_responses_false_skips_chat2_write(self, make_proc, prompt_builder, llm_adapter):
        """When save_responses is False, _ensure_chat2_session is never called."""
        from tests.conftest import FakeAgent

        mock_store = Mock()
        mock_store.session_exists.return_value = False
        mock_store.create_session.return_value = Mock()
        mock_store.add_events.return_value = []

        proc = make_proc()
        proc.chat2_store = mock_store

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "transient"

        out = proc.process_message(
            primary_agent=FakeAgent(save_responses=False),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="should_not_be_used",
        )

        assert out == "transient"
        mock_store.session_exists.assert_not_called()
        mock_store.create_session.assert_not_called()


# ---------------------------------------------------------------------------
# FCP supports_images passthrough tests
# ---------------------------------------------------------------------------


class TestFCPSupportsImagesPassthrough:
    """Verify FCP queries supports_image_processing and passes result to build_prompt."""

    def test_fcp_passes_supports_images_true_for_vision_model(self, make_proc, prompt_builder, llm_adapter):
        """When model supports images, FCP passes supports_images=True to build_prompt."""
        from tests.conftest import FakeAgent

        proc = make_proc()
        llm_adapter.supports_image_processing.return_value = True
        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "ok"

        proc.process_message(
            primary_agent=FakeAgent(model="gpt-5-mini", save_responses=False),
            account={"accountId": "acct1"},
            message="describe this image",
            conversation_id="c1",
            context_name="ctx",
            image_ids=["img001"],
        )

        # Verify supports_image_processing was called with the model
        llm_adapter.supports_image_processing.assert_called_once_with("gpt-5-mini", None)

        # Verify build_prompt received supports_images=True
        build_kwargs = prompt_builder.build_prompt.call_args.kwargs
        assert build_kwargs["supports_images"] is True

    def test_fcp_passes_supports_images_false_for_text_model(self, make_proc, prompt_builder, llm_adapter):
        """When model doesn't support images, FCP passes supports_images=False to build_prompt."""
        from tests.conftest import FakeAgent

        proc = make_proc()
        llm_adapter.supports_image_processing.return_value = False
        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "ok"

        proc.process_message(
            primary_agent=FakeAgent(model="deepseek-v4-pro", save_responses=False),
            account={"accountId": "acct1"},
            message="describe this image",
            conversation_id="c1",
            context_name="ctx",
            image_ids=["img001"],
        )

        # Verify supports_image_processing was called with the model
        llm_adapter.supports_image_processing.assert_called_once_with("deepseek-v4-pro", None)

        # Verify build_prompt received supports_images=False
        build_kwargs = prompt_builder.build_prompt.call_args.kwargs
        assert build_kwargs["supports_images"] is False

    def test_fcp_streaming_passes_supports_images(self, make_proc, prompt_builder, llm_adapter):
        """Streaming path also passes supports_images to build_prompt."""
        from tests.conftest import FakeAgent

        proc = make_proc()
        llm_adapter.supports_image_processing.return_value = False
        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "ok"

        # Consume the generator
        list(proc.process_message_streaming(
            primary_agent=FakeAgent(model="deepseek-v4-flash", save_responses=False),
            account={"accountId": "acct1"},
            message="describe this image",
            conversation_id="c1",
            context_name="ctx",
            image_ids=["img001"],
        ))

        # Verify build_prompt received supports_images=False
        build_kwargs = prompt_builder.build_prompt.call_args.kwargs
        assert build_kwargs["supports_images"] is False


# ---------------------------------------------------------------------------
# Context mandatory_tools merge tests
# ---------------------------------------------------------------------------


def _make_context_state(data):
    from src.storage.models import Context

    return Context(
        id="ctx",
        account_name="acct1",
        mandatory_tools=list(data.get("mandatory_tools", [])),
        text=data.get("text", ""),
        extra={k: v for k, v in data.items() if k not in ("mandatory_tools", "text")},
        updated_at=None,
    )


def _agent_allowing(allowed_tools):
    from tests.conftest import FakeAgent

    agent = FakeAgent(save_responses=False)
    agent.allowed_tools = list(allowed_tools)
    return agent


def _tools_passed_to_model(llm_adapter):
    """Return the tool defs sent to the main model on the most recent call."""
    return llm_adapter.call_model.call_args.kwargs["tools"]


def test_mandatory_tools_merged_after_lazy_selection(make_proc, prompt_builder, llm_adapter, config):
    """Context mandatory_tools are restored after lazy selection dropped them."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
            {"name": "web_search_handler", "description": "search the web"},
        ],
        handler_by_name={},
    )
    config.values["lazy_tool_loading"] = {"enabled": True, "min_eligible_to_select": 2}

    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "execute_command", "web_search_handler"])

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": ["execute_command", "file_load"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "I ate a snack at 10:00 am"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "logged"

    # Lazy selection only keeps web_search_handler; mandatory tools must come back.
    active = [{"name": "web_search_handler", "description": "search the web"}]
    with patch(
        "src.message_processors.function_calling_processor.select_active_tool_defs",
        return_value=(active, {"active_count": 1}),
    ) as select_mock:
        out = proc.process_message(
            primary_agent=agent,
            account={"accountId": "acct1"},
            message="I ate a snack at 10:00 am of grilled chicken 1 serving",
            conversation_id="c1",
            context_name="food_diary",
        )

    assert out == "logged"
    select_mock.assert_called_once()
    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    # Mandatory tools first (front-insert), then the lazy-selected active set.
    assert names == ["execute_command", "file_load", "web_search_handler"]


def test_mandatory_tools_deduplicated(make_proc, prompt_builder, llm_adapter, config):
    """Repeated names in mandatory_tools and names already present are not re-added."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
            {"name": "web_search_handler", "description": "search the web"},
        ],
        handler_by_name={},
    )
    config.values["lazy_tool_loading"] = {"enabled": True, "min_eligible_to_select": 2}

    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "execute_command", "web_search_handler"])

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": ["execute_command", "execute_command", "web_search_handler"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    active = [{"name": "web_search_handler", "description": "search the web"}]
    with patch(
        "src.message_processors.function_calling_processor.select_active_tool_defs",
        return_value=(active, {"active_count": 1}),
    ):
        proc.process_message(
            primary_agent=agent,
            account={"accountId": "acct1"},
            message="x",
            conversation_id="c1",
            context_name="food_diary",
        )

    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    # execute_command added once despite appearing twice; web_search_handler
    # was already present so it is not duplicated.
    assert names == ["execute_command", "web_search_handler"]


def test_mandatory_tool_outside_agent_allowed_tools_is_skipped(make_proc, prompt_builder, llm_adapter):
    """Mandatory tools outside agent.allowed_tools are logged and skipped (hard ceiling)."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "execute_command", "description": "run a command"},
            {"name": "file_load", "description": "load a file"},
        ],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load"])  # execute_command NOT allowed for this agent

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": ["execute_command"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    )

    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    assert names == ["file_load"]


def test_mandatory_tool_unknown_to_registry_is_ignored(make_proc, prompt_builder, llm_adapter):
    """Unknown mandatory tool names are logged and ignored without crashing."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
        ],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "execute_command", "ghost_tool"])

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": ["ghost_tool", "execute_command"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    )

    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    # Nothing was added, so the original registry order is preserved.
    assert names == ["file_load", "execute_command"]


def test_mandatory_tools_non_list_is_ignored(make_proc, prompt_builder, llm_adapter):
    """A non-list mandatory_tools value is ignored without crashing."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[{"name": "file_load", "description": "load a file"}],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load"])

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": "file_load"}  # string, not a list
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    )

    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    assert names == ["file_load"]


def test_mandatory_tools_merged_in_streaming_path(make_proc, prompt_builder, llm_adapter, config):
    """The streaming path applies the same mandatory-tools merge."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
            {"name": "web_search_handler", "description": "search the web"},
        ],
        handler_by_name={},
    )
    config.values["lazy_tool_loading"] = {"enabled": True, "min_eligible_to_select": 2}

    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "execute_command", "web_search_handler"])

    prompt_builder._get_context_state.return_value = _make_context_state(
        {"mandatory_tools": ["execute_command", "file_load"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "snack"}]

    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    active = [{"name": "web_search_handler", "description": "search the web"}]
    with patch(
        "src.message_processors.function_calling_processor.select_active_tool_defs",
        return_value=(active, {"active_count": 1}),
    ):
        events = list(proc.process_message_streaming(
            primary_agent=agent,
            account={"accountId": "acct1"},
            message="I ate a snack",
            conversation_id="c1",
            context_name="food_diary",
        ))

    assert any("done" in e for e in events)
    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    assert names == ["execute_command", "file_load", "web_search_handler"]

def test_unknown_tool_returns_recoverable_error_to_llm(make_proc, prompt_builder, llm_adapter, storage):
    from tests.conftest import FakeRegistry, FakeAgent

    reg = FakeRegistry(handler_by_name={}, tool_defs=[{"name": "known"}])
    proc = make_proc(registry=reg, storage=storage)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    resp1, resp2 = object(), object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]
    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "bash", "id": "call-1", "arguments": "{}"}],
        [],
    ]
    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }
    llm_adapter.get_text.return_value = "ok"

    out = proc.process_message(
        primary_agent=FakeAgent(save_responses=False, max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="run it",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "ok"

    # The unknown tool was converted into an error output for the LLM rather
    # than crashing the request.
    second_call_input = llm_adapter.call_model.call_args_list[1].kwargs["input"]
    assert second_call_input[0]["call_id"] == "call-1"
    assert "Unknown tool 'bash'" in second_call_input[0]["output"]
    assert "known" in second_call_input[0]["output"]

