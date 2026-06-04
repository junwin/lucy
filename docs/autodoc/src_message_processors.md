---
tags:
  - processor
  - messageprocessorinterface
  - abc
  - process_message
  - protocol
  - injector
  - processorfactoryinterface
  - import
  - path
  - functioncallingprocessor
  - src/message_processors
---

# Module: `src/message_processors`

## Source Files

| File | Description |
|------|-------------|
| `__init__.py` | Empty |
| `message_processor_interface.py` | Base interface + factory protocol |
| `types.py` | Type aliases (`AgentDict`, `AccountDict`, `OptionalAgentDict`) |
| `processor_factory.py` | `ProcessorFactory` — maps names to import paths, uses `Injector` |
| `function_calling_processor.py` | `FunctionCallingProcessor` — main LLM tool-calling processor |
| `automation_processor.py` | `AutomationProcessor` — executes persisted tasklists |
| `task_running_processor.py` | `TaskRunningProcessor` — scaffold for step 3.2 |

## Key Classes

| Class | Kind | Role |
|-------|------|------|
| `MessageProcessorInterface` | ABC | Base interface with abstract `process_message()` |
| `ProcessorFactoryInterface` | Protocol | Factory protocol with `get()` |
| `ProcessorFactory` | Concrete | Maps processor names to import paths, constructs via `Injector` |
| `FunctionCallingProcessor` | Concrete | Main LLM tool-calling processor |
| `AutomationProcessor` | Concrete | Tasklist execution processor |
| `TaskRunningProcessor` | Concrete | Scaffold processor |
| `_ProcessorContext` | Dataclass | Internal context holder |
| `_ToolCall` | Dataclass | Internal tool call wrapper |
| `ToolResultTooLargeError` | Exception | Raised when tool result exceeds size limit |
| `ToolHandlerError` | Exception | Raised when a tool handler fails |

## Dependencies

**Internal:**
- `src.agent`
- `src.config_manager`
- `src.storage.base`, `src.storage.models`
- `src.handlers.handler_registry`
- `src.prompt_builders.prompt_builder_interface`
- `src.llm.adapter_interface`
- `src.chat2.facade`, `src.chat2.models`
- `src.tasklists.task`, `src.tasklists.task_list`, `src.tasklists.task_states`

**External:**
- `injector`
- `json`, `logging`, `time`, `datetime`, `typing`, `abc`

## Base Interface Methods

### `MessageProcessorInterface.process_message()`

```python
@abstractmethod
def process_message(
    self,
    *,
    primary_agent: Agent,
    account: AccountDict,
    message: str,
    conversation_id: str = "0",
    context_name: str = "",
    secondary_agent: Optional[Agent] = None,
    processor_factory: Optional[Any] = None,
) -> str:
    pass
```

### `ProcessorFactoryInterface.get()`

```python
def get(self, processor_name: str) -> MessageProcessorInterface:
    ...
```

## Key Methods on Concrete Classes

### `FunctionCallingProcessor`

| Method | Visibility | Purpose |
|--------|-----------|---------|
| `process_message()` | public | Entry point — builds context, prompt, runs LLM loop |
| `_run_llm_loop()` | private | Iterative LLM call + tool execution loop |
| `_execute_tool_calls()` | private | Executes tool handlers for a batch of tool calls |
| `_execute_simple_tasklist()` | private | Delegates tasklist execution to a worker agent |
| `_build_context()` | private | Constructs `_ProcessorContext` from agent config |
| `_wrap_tool_calls()` | private | Wraps raw tool call dicts into `_ToolCall` objects |
| `_get_environment_system_messages()` | private | Reads `environment_prompt_block` config |
| `_tool_calls_are_duplicate()` | private | Detects repeated identical tool calls |
| `_safe_json_loads()` | private | Safely parses JSON tool arguments |
| `_tool_result_to_text()` | private | Serializes tool result, enforces size limit |
| `_ensure_chat2_session()` | private | Creates chat2 session if missing |
| `_write_chat2_events()` | private | Writes user + assistant events to chat2 |

### `AutomationProcessor`

| Method | Visibility | Purpose |
|--------|-----------|---------|
| `process_message()` | public | Entry point — parses JSON command, delegates to `execute_tasklist()` |
| `execute_tasklist()` | public | Core execution loop — finds pending tasks, runs them via FCP |
| `_ensure_chat2_session()` | private | Creates chat2 session if missing |
| `_write_chat2_event()` | private | Writes a single event to chat2 |

### `TaskRunningProcessor`

| Method | Visibility | Purpose |
|--------|-----------|---------|
| `process_message()` | public | Parses JSON command, finds next pending task (no execution) |
