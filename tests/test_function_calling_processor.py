import pytest
from unittest.mock import Mock


class FakeConfig:
    def __init__(self, values=None):
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)


class FakeStorage:
    def __init__(self):
        self.messages = []

    def append_chat_message(self, conversation_id, chat_message):
        self.messages.append((conversation_id, chat_message))


class FakeHandler:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = []

    def execute(self, args, account_name=None):
        self.calls.append((args, account_name))
        if self._exc is not None:
            raise self._exc
        return self._result


class FakeRegistry:
    def __init__(self, handler_by_name=None, tool_defs=None):
        self._handler_by_name = handler_by_name or {}
        self._tool_defs = tool_defs if tool_defs is not None else []

    def tools(self):
        return self._tool_defs

    def create(self, name, config=None):
        return self._handler_by_name[name]


class FakeAgent:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "lucy")
        self.model = kwargs.get("model", "test-model")
        self.temperature = kwargs.get("temperature", 0.0)
        self.context_type = kwargs.get("context_type", "hybrid")
        self.max_function_call_iterations = kwargs.get("max_function_call_iterations", 5)
        self.save_responses = kwargs.get("save_responses", False)
        self.delegation_depth = kwargs.get("delegation_depth", 0)
        self.max_delegation_depth = kwargs.get("max_delegation_depth", 1)


def _make_processor(*, registry=None, storage=None, config=None):
    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=config or FakeConfig(),
        registry=registry or FakeRegistry(),
        storage=storage or FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )
    return proc, prompt_builder, llm_adapter


def test_no_tool_calls_returns_text():
    proc, prompt_builder, llm_adapter = _make_processor()

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]

    resp = object()
    llm_adapter.call_model.return_value = resp
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = "hello!"

    out = proc.process_message(
        primary_agent=FakeAgent(save_responses=False),
        account={"accountId": "acct1"},
        message="hi",
        conversation_id="c1",
    )

    assert out == "hello!"
    assert llm_adapter.call_model.call_count == 1


def test_tool_call_executes_handler_and_chains():
    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    handler = FakeHandler({"ok": True, "value": 123})
    registry = FakeRegistry(
        handler_by_name={"my_tool": handler},
        tool_defs=[{"name": "my_tool"}],
    )
    storage = FakeStorage()

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=storage,
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "do thing"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]

    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "my_tool", "id": "call-1", "arguments": "{\"x\": 1}"}],
        [],
    ]

    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{\"ok\": true}",
    }

    llm_adapter.get_text.return_value = "done"

    out = proc.process_message(
        primary_agent=FakeAgent(save_responses=False, max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="do thing",
        conversation_id="c1",
    )

    assert out == "done"
    assert handler.calls == [({"x": 1}, "acct1")]

    first_call_kwargs = llm_adapter.call_model.call_args_list[0].kwargs
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs

    assert first_call_kwargs["previous_response_id"] is None
    assert second_call_kwargs["previous_response_id"] == "r1"
    assert second_call_kwargs["input"] == [llm_adapter.format_tool_output.return_value]


def test_tool_calls_without_response_id_raises():
    from src.message_processors.function_calling_processor import ToolHandlerError

    proc, prompt_builder, llm_adapter = _make_processor(
        registry=FakeRegistry(
            handler_by_name={"t": FakeHandler({"ok": True})},
            tool_defs=[{"name": "t"}],
        )
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "x"}]

    resp = object()
    llm_adapter.call_model.return_value = resp
    llm_adapter.get_response_id.return_value = None
    llm_adapter.extract_tool_calls.return_value = [{"name": "t", "id": "c1", "arguments": "{}"}]

    with pytest.raises(ToolHandlerError):
        proc.process_message(
            primary_agent=FakeAgent(),
            account={"accountId": "acct1"},
            message="x",
            conversation_id="c1",
        )


def test_max_iterations_exceeded_returns_limit_message():
    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    handler = FakeHandler({"ok": True})
    registry = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "loop"}]

    resp1 = object()
    llm_adapter.call_model.return_value = resp1
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [
        {"name": "my_tool", "id": "call-1", "arguments": "{}"}
    ]
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
    )

    assert "internal limit" in out.lower()
    assert llm_adapter.call_model.call_count == 1


def test_bad_json_tool_args_falls_back_to_empty_dict():
    """If tool arguments are not valid JSON, processor should call handler with {}."""

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    handler = FakeHandler({"ok": True})
    registry = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "bad json"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]

    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "my_tool", "id": "call-1", "arguments": "{not-json"}],
        [],
    ]

    llm_adapter.format_tool_output.return_value = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{}",
    }
    llm_adapter.get_text.return_value = "ok"

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="bad json",
        conversation_id="c1",
    )

    assert out == "ok"
    assert handler.calls == [({}, "acct1")]


def test_tool_result_too_large_is_converted_to_error_tool_output_and_model_called_again():
    """If handler raises ToolResultTooLargeError, processor should send an error tool output and continue."""

    from src.message_processors.function_calling_processor import (
        FunctionCallingProcessor,
        ToolResultTooLargeError,
    )

    handler = FakeHandler(exc=ToolResultTooLargeError("too big"))
    registry = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "big"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]

    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "my_tool", "id": "call-1", "arguments": "{}"}],
        [],
    ]

    # We want to see what the processor passes into format_tool_output
    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "recovered"

    out = proc.process_message(
        primary_agent=FakeAgent(max_function_call_iterations=3),
        account={"accountId": "acct1"},
        message="big",
        conversation_id="c1",
    )

    assert out == "recovered"
    assert llm_adapter.call_model.call_count == 2

    # Second call should include tool output (error payload)
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    assert second_call_kwargs["previous_response_id"] == "r1"
    assert len(second_call_kwargs["input"]) == 1

    tool_output = second_call_kwargs["input"][0]
    assert tool_output["call_id"] == "call-1"
    assert "error" in str(tool_output["output"]).lower()


def test_handler_exception_is_wrapped_in_tool_handler_error():
    from src.message_processors.function_calling_processor import ToolHandlerError

    handler = FakeHandler(exc=RuntimeError("boom"))
    registry = FakeRegistry(handler_by_name={"my_tool": handler}, tool_defs=[{"name": "my_tool"}])

    proc, prompt_builder, llm_adapter = _make_processor(registry=registry)

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "explode"}]

    resp1 = object()
    llm_adapter.call_model.return_value = resp1
    llm_adapter.get_response_id.return_value = "r1"
    llm_adapter.extract_tool_calls.return_value = [
        {"name": "my_tool", "id": "call-1", "arguments": "{}"}
    ]

    with pytest.raises(ToolHandlerError):
        proc.process_message(
            primary_agent=FakeAgent(max_function_call_iterations=2),
            account={"accountId": "acct1"},
            message="explode",
            conversation_id="c1",
        )


def test_plan_tasks_tasklist_executes_worker_tasks_and_returns_summary():
    """If plan_tasks returns a tasklist and secondary_agent+processor_factory are provided,
    FunctionCallingProcessor should execute the tasklist via _execute_simple_tasklist.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    # plan_tasks returns a tasklist with 2 tasks for worker agent 'colin'
    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "Do two things",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "First",
                "agent": "colin",
                "instruction": "Do first",
            },
            {
                "id": "task-2",
                "type": "task",
                "title": "Second",
                "agent": "colin",
                "instruction": "Do second",
            },
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    # First model call triggers plan_tasks tool call; second returns final text
    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "all done"

    # Worker agent and processor_factory
    worker = FakeAgent(name="colin")

    class FakeProcessorFactory:
        pass

    # Patch proc.process_message so that when _execute_simple_tasklist calls it for worker tasks,
    # it returns deterministic strings (and does not recurse into tool calling).
    original_process_message = proc.process_message

    def _process_message_side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            return f"worker_result: {message[:20]}"
        return original_process_message(primary_agent=primary_agent, message=message, **kwargs)

    proc.process_message = Mock(side_effect=_process_message_side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=2),
        secondary_agent=worker,
        processor_factory=FakeProcessorFactory(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "all done"

    # Ensure worker tasks were executed (2 calls for colin)
    worker_calls = [
        c for c in proc.process_message.call_args_list if c.kwargs.get("primary_agent").name == "colin"
    ]
    assert len(worker_calls) == 2

    # Ensure the second LLM call was chained with tool output
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    assert second_call_kwargs["previous_response_id"] == "r1"
    assert len(second_call_kwargs["input"]) == 1
    assert second_call_kwargs["input"][0]["call_id"] == "call-1"
    assert "tasks" in second_call_kwargs["input"][0]["output"]


def test_plan_tasks_tasklist_refuses_when_max_delegation_depth_exceeded():
    """If delegation_depth >= max_delegation_depth, _execute_simple_tasklist should refuse.

    This is the safety check that prevents infinite delegation.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "Do two things",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "First",
                "agent": "colin",
                "instruction": "Do first",
            }
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "final"

    # If delegation is refused, worker should never be called.
    worker = FakeAgent(name="colin")

    # Patch proc.process_message to detect any worker execution attempts.
    original_process_message = proc.process_message

    def _process_message_side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            raise AssertionError("Worker agent should not be called when delegation depth exceeded")
        return original_process_message(primary_agent=primary_agent, message=message, **kwargs)

    proc.process_message = Mock(side_effect=_process_message_side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(
            name="lucy",
            max_delegation_depth=1,
            delegation_depth=1,  # already at max
        ),
        secondary_agent=worker,
        processor_factory=object(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "final"

    # Ensure the tool output contains the refusal error
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    tool_output = second_call_kwargs["input"][0]
    assert "max delegation depth" in tool_output["output"].lower()


def test_plan_tasks_tasklist_unknown_agent_returns_error_per_task_and_still_completes():
    """If a tasklist contains a task for an unknown agent name, _execute_simple_tasklist
    should mark that task as ok=False with an 'Unknown agent' error, and still return a summary.

    This protects refactors around delegation routing.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "Mixed agents",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "Unknown agent task",
                "agent": "not-colin",
                "instruction": "Do something",
            },
            {
                "id": "task-2",
                "type": "task",
                "title": "Known agent task",
                "agent": "colin",
                "instruction": "Do known",
            },
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "final"

    worker = FakeAgent(name="colin")

    # Patch proc.process_message so worker execution is deterministic.
    original_process_message = proc.process_message

    def _process_message_side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            return "worker ok"
        return original_process_message(primary_agent=primary_agent, message=message, **kwargs)

    proc.process_message = Mock(side_effect=_process_message_side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=3),
        secondary_agent=worker,
        processor_factory=object(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "final"

    # Tool output should include both tasks, with one unknown-agent error.
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    tool_output_text = second_call_kwargs["input"][0]["output"]

    assert "Unknown agent" in tool_output_text
    assert "not-colin" in tool_output_text
    assert "worker ok" in tool_output_text


def test_plan_tasks_tasklist_missing_instruction_marks_task_error_and_continues():
    """If a task in the tasklist is missing 'instruction', the executor should not crash.

    It should mark that task as ok=False and still execute other valid tasks.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "One bad task",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "Missing instruction",
                "agent": "colin",
                # instruction intentionally missing
            },
            {
                "id": "task-2",
                "type": "task",
                "title": "Good task",
                "agent": "colin",
                "instruction": "Do good",
            },
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "final"

    worker = FakeAgent(name="colin")

    # Patch proc.process_message so worker execution is deterministic.
    original_process_message = proc.process_message

    def _process_message_side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            return "worker ok"
        return original_process_message(primary_agent=primary_agent, message=message, **kwargs)

    proc.process_message = Mock(side_effect=_process_message_side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=3),
        secondary_agent=worker,
        processor_factory=object(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "final"

    # Tool output should include an error for the missing-instruction task
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    tool_output_text = second_call_kwargs["input"][0]["output"]

    assert "task-1" in tool_output_text
    assert "instruction" in tool_output_text.lower()
    assert "worker ok" in tool_output_text


def test_plan_tasks_tasklist_missing_agent_marks_task_error_and_continues():
    """If a task in the tasklist is missing 'agent', the executor should not crash.

    It should mark that task as ok=False and still execute other valid tasks.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "One bad task",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "Missing agent",
                # agent intentionally missing
                "instruction": "Do something",
            },
            {
                "id": "task-2",
                "type": "task",
                "title": "Good task",
                "agent": "colin",
                "instruction": "Do good",
            },
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "final"

    worker = FakeAgent(name="colin")

    # Patch proc.process_message so worker execution is deterministic.
    original_process_message = proc.process_message

    def _process_message_side_effect(*, primary_agent, message, **kwargs):
        if primary_agent.name == "colin":
            return "worker ok"
        return original_process_message(primary_agent=primary_agent, message=message, **kwargs)

    proc.process_message = Mock(side_effect=_process_message_side_effect)

    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=3),
        secondary_agent=worker,
        processor_factory=object(),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "final"

    # Tool output should include an error for the missing-agent task
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    tool_output_text = second_call_kwargs["input"][0]["output"]

    assert "task-1" in tool_output_text
    assert "agent" in tool_output_text.lower()
    assert "worker ok" in tool_output_text


def test_plan_tasks_tasklist_worker_agent_not_provided_returns_clear_error():
    """If a tasklist contains tasks for the worker agent name, but secondary_agent is not provided,
    the executor should return a clear error instead of trying to delegate.

    This protects refactors around optional delegation wiring.
    """

    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    plan_tasks_result = {
        "ok": True,
        "tool": "plan_tasks",
        "kind": "tasklist",
        "description": "Needs worker",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "Worker task",
                "agent": "colin",
                "instruction": "Do work",
            }
        ],
    }

    plan_handler = FakeHandler(plan_tasks_result)

    registry = FakeRegistry(
        handler_by_name={"plan_tasks": plan_handler},
        tool_defs=[{"name": "plan_tasks"}],
    )

    prompt_builder = Mock()
    llm_adapter = Mock()

    proc = FunctionCallingProcessor(
        config=FakeConfig(),
        registry=registry,
        storage=FakeStorage(),
        prompt_builder=prompt_builder,
        llm_adapter=llm_adapter,
    )

    prompt_builder.build_prompt.return_value = [{"role": "user", "content": "plan"}]

    resp1 = object()
    resp2 = object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = ["r1", "r2"]

    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": "plan_tasks", "id": "call-1", "arguments": "{\"goal\": \"x\"}"}],
        [],
    ]

    llm_adapter.format_tool_output.side_effect = lambda call_id, output: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }

    llm_adapter.get_text.return_value = "final"

    # No secondary_agent passed
    out = proc.process_message(
        primary_agent=FakeAgent(name="lucy", max_delegation_depth=3),
        account={"accountId": "acct1"},
        message="plan",
        conversation_id="c1",
        context_name="ctx",
    )

    assert out == "final"

    # Tool output should include a clear error about missing secondary_agent/worker
    second_call_kwargs = llm_adapter.call_model.call_args_list[1].kwargs
    tool_output_text = second_call_kwargs["input"][0]["output"]

    assert "secondary_agent" in tool_output_text or "worker" in tool_output_text.lower()
