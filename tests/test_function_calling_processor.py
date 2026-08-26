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
    ).text

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
    ).text

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
    ).text

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
    ).text

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
    llm_adapter.format_tool_output.side_effect = lambda call_id, output, **kwargs: {
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
    ).text

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
    llm_adapter.format_tool_output.side_effect = lambda call_id, output, **kwargs: {
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
    ).text

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
        ).text

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
        ).text

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


def test_fcp_uses_tool_selection_pipeline(make_proc, prompt_builder, llm_adapter):
    """The FCP delegates tool-list resolution to ToolSelectionPipeline and
    passes its resolved active defs to the main model."""
    from tests.conftest import FakeAgent

    proc = make_proc()
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    active_defs = [{"name": "file_load", "description": "load a file"}]
    with patch(
        "src.message_processors.function_calling_processor.ToolSelectionPipeline"
    ) as pipeline_cls:
        pipeline_cls.return_value.get_tool_handler_defs.return_value = active_defs
        proc.process_message(
            primary_agent=FakeAgent(save_responses=False),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id="c1",
            context_name="ctx",
        )

    # Constructed with the FCP's real dependencies.
    pipeline_cls.assert_called_once()
    kwargs = pipeline_cls.call_args.kwargs
    assert kwargs["registry"] is proc.registry
    assert kwargs["llm_adapter"] is proc.llm_adapter
    assert kwargs["config"] is proc.config

    # The pipeline's resolved active defs reached the main model.
    assert _tools_passed_to_model(llm_adapter) == active_defs


def test_required_tools_survive_lazy_selection(make_proc, prompt_builder, llm_adapter, storage, config):
    """Context required tools stay active even when prompt-based selection
    drops them; required tools come first (issue #126 pipeline semantics)."""
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

    storage.contexts[("acct1", "food_diary")] = _make_context_state(
        {"mandatory_tools": ["execute_command", "file_load"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    # The selection LLM only suggests web_search_handler; required tools must
    # still be present (and ordered first).
    with patch(
        "src.tool_selection.pipeline.query_llm",
        return_value=["web_search_handler"],
    ):
        proc.process_message(
            primary_agent=agent,
            account={"accountId": "acct1"},
            message="x",
            conversation_id="c1",
            context_name="food_diary",
        )

    names = [t["name"] for t in _tools_passed_to_model(llm_adapter)]
    assert names == ["execute_command", "file_load", "web_search_handler"]


def test_required_tool_not_permissioned_returns_error(make_proc, prompt_builder, llm_adapter, storage):
    """A required tool outside agent.allowed_tools raises required_not_permissioned."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
        ],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load"])  # execute_command NOT allowed

    storage.contexts[("acct1", "food_diary")] = _make_context_state(
        {"mandatory_tools": ["execute_command"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    out = proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    ).text

    assert "not permissioned" in out
    assert "execute_command" in out


def test_required_tool_not_registered_returns_error(make_proc, prompt_builder, llm_adapter, storage):
    """A required tool unknown to the registry raises required_not_registered."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[{"name": "file_load", "description": "load a file"}],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "ghost_tool"])

    storage.contexts[("acct1", "food_diary")] = _make_context_state(
        {"mandatory_tools": ["ghost_tool"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    out = proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    ).text

    assert "not registered" in out
    assert "ghost_tool" in out


def test_budget_exceeded_returns_error(make_proc, prompt_builder, llm_adapter, config):
    """Over-cap schemas raise budget_exceeded instead of silently trimming."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file " * 40},
            {"name": "execute_command", "description": "run a command " * 40},
        ],
        handler_by_name={},
    )
    config.values["max_handler_schema_tokens"] = 1
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load", "execute_command"])

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    out = proc.process_message(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="ctx",
    ).text

    assert "budget" in out


def test_required_tool_not_permissioned_in_streaming_path(make_proc, prompt_builder, llm_adapter, storage):
    """The streaming path surfaces a required-tool error as an SSE error event."""
    from tests.conftest import FakeRegistry

    reg = FakeRegistry(
        tool_defs=[
            {"name": "file_load", "description": "load a file"},
            {"name": "execute_command", "description": "run a command"},
        ],
        handler_by_name={},
    )
    proc = make_proc(registry=reg)

    agent = _agent_allowing(["file_load"])

    storage.contexts[("acct1", "food_diary")] = _make_context_state(
        {"mandatory_tools": ["execute_command"]}
    )
    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "ok"

    events = list(proc.process_message_streaming(
        primary_agent=agent,
        account={"accountId": "acct1"},
        message="x",
        conversation_id="c1",
        context_name="food_diary",
    ))

    assert any("error" in e and "not permissioned" in e for e in events)
    assert any("done" in e for e in events)


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
    llm_adapter.format_tool_output.side_effect = lambda call_id, output, **kwargs: {
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
    ).text

    assert out == "ok"

    # The unknown tool was converted into an error output for the LLM rather
    # than crashing the request.
    second_call_input = llm_adapter.call_model.call_args_list[1].kwargs["input"]
    assert second_call_input[0]["call_id"] == "call-1"
    assert "Unknown tool 'bash'" in second_call_input[0]["output"]
    assert "known" in second_call_input[0]["output"]


def test_streaming_persists_on_generator_close(make_proc, prompt_builder, llm_adapter):
    """When the client disconnects mid-stream (generator close), streamed events are still persisted to chat2."""
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

    gen = proc.process_message_streaming(
        primary_agent=FakeAgent(save_responses=True),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
        context_name="ctx",
    )

    # Consume the first SSE event, then simulate the client disconnecting.
    next(gen)
    gen.close()

    # The finally block must persist the streamed events to chat2.
    mock_store.add_events.assert_called()

# ---------------------------------------------------------------------------
# Step 0 golden test (fcp-split): non-streaming vs streaming final-text equivalence
# ---------------------------------------------------------------------------


def test_streaming_and_nonstreaming_paths_produce_same_final_text(make_proc, prompt_builder, llm_adapter, storage):
    """Golden equivalence test (fcp-split design doc Step 0).

    Runs the SAME LLM/tool sequence through both public paths:
      - process_message()            -> returns the final text string
      - process_message_streaming()  -> yields SSE-formatted strings
    The payload of the last 'text' SSE event must equal the non-streaming
    final text. This locks the Step 4 loop-collapse equivalence.
    """
    import json

    from tests.conftest import FakeAgent, FakeHandler, FakeRegistry, setup_tool_then_text

    handler = FakeHandler({"ok": True, "value": 42})
    reg = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])
    proc = make_proc(registry=reg, storage=storage)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "do thing"}]

    request_kwargs = dict(
        primary_agent=FakeAgent(save_responses=False, max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="do thing",
        conversation_id="c1",
        context_name="ctx",
    )

    # ── Non-streaming path ──
    setup_tool_then_text(llm_adapter, tool_name="my_tool", tool_args='{"x": 1}', final_text="done")
    final_text = proc.process_message(**request_kwargs).text
    assert final_text == "done"

    # ── Streaming path: same LLM/tool sequence, fresh mock state ──
    llm_adapter.reset_mock()
    setup_tool_then_text(llm_adapter, tool_name="my_tool", tool_args='{"x": 1}', final_text="done")

    text_payloads = []
    for sse in proc.process_message_streaming(**request_kwargs):
        # The public streaming path yields SSE wire strings ("data: {json}\n\n").
        payload = json.loads(sse[len("data: "):].strip())
        if payload.get("type") == "text":
            text_payloads.append(payload["content"])

    assert text_payloads, "streaming path should emit at least one text event"
    assert text_payloads[-1] == final_text
