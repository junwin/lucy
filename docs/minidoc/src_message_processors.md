---
tags:
  - src_message_processors
  - lucyproject
  - MessageProcessorInterface
  - FunctionCallingProcessor
  - AutomationProcessor
  - TaskRunningProcessor
  - ProcessorFactory
  - ToolHandlerError
  - ToolResultTooLargeError
---

# Module: `src/message_processors`

## Summary

Message processing orchestration layer. Defines the abstract interface for processing user messages and provides concrete implementations:

- **`FunctionCallingProcessor`** — the primary LLM-driven processor. Builds prompts, calls the LLM with tool definitions, executes tool calls in a loop (with duplicate detection and iteration caps), and writes events to chat2 storage.
- **`AutomationProcessor`** — executes persisted tasklists. Parses JSON commands (`run`/`execute`/`start`), finds pending tasks, delegates execution to `FunctionCallingProcessor`, and persists task state after each step.
- **`TaskRunningProcessor`** — scaffold processor (agent: `doris`). Parses JSON commands and finds the next pending task from a persisted tasklist, but does **not** execute it yet.

Also provides `ProcessorFactory` (lazy-loading, injector-based construction) and shared type aliases.

## Key Classes

| Class | File | Description |
|---|---|---|
| `MessageProcessorInterface` | `message_processor_interface.py` | Abstract base class (ABC) for all processors |
| `ProcessorFactoryInterface` | `message_processor_interface.py` | Protocol for factory that returns processors by name |
| `ProcessorFactory` | `processor_factory.py` | Concrete factory — maps processor names to import paths, constructs via `Injector` |
| `FunctionCallingProcessor` | `function_calling_processor.py` | LLM-driven tool-calling processor (primary) |
| `AutomationProcessor` | `automation_processor.py` | Tasklist execution engine |
| `TaskRunningProcessor` | `task_running_processor.py` | Scaffold — finds next pending task (agent: doris) |
| `ToolHandlerError` | `function_calling_processor.py` | Raised when a tool handler fails |
| `ToolResultTooLargeError` | `function_calling_processor.py` | Raised when a tool result exceeds `max_tool_result_chars` |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Empty init |
| `message_processor_interface.py` | `MessageProcessorInterface` (ABC) + `ProcessorFactoryInterface` (Protocol) |
| `types.py` | Type aliases: `AgentDict`, `AccountDict`, `OptionalAgentDict` |
| `processor_factory.py` | `ProcessorFactory` — lazy-import, injector-based construction |
| `function_calling_processor.py` | `FunctionCallingProcessor` — LLM loop, tool execution, chat2 events |
| `automation_processor.py` | `AutomationProcessor` — tasklist execution, state persistence, chat2 events |
| `task_running_processor.py` | `TaskRunningProcessor` — scaffold for finding next pending task |

## Dependencies

- **`src.agent`** — `Agent` class
- **`src.config_manager`** — `ConfigManager`
- **`src.handlers.handler_registry`** — `HandlerRegistry`
- **`src.prompt_builders.prompt_builder_interface`** — `PromptBuilderInterface`
- **`src.llm.adapter_interface`** — `LLMAdapter`
- **`src.chat2.facade`** — `Chat2Store`
- **`src.chat2.models`** — `ChatEvent`
- **`src.storage.base`** — `Storage` (used by `AutomationProcessor`, `TaskRunningProcessor`)
- **`src.storage.models`** — `ChatMessage`
- **`src.tasklists`** — `Task`, `TaskList`, task state constants
- **`injector`** — dependency injection (`@inject`)
- **stdlib** — `abc`, `json`, `logging`, `time`, `datetime`, `dataclasses`, `typing`

## Methods — `MessageProcessorInterface` (ABC)

| Method | Signature | Description |
|---|---|---|
| `process_message` | `(self, *, primary_agent, account, message, conversation_id, context_name, secondary_agent, processor_factory) -> str` | Abstract — process a user message and return a response string |

## Methods — `FunctionCallingProcessor`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, config, registry, prompt_builder, llm_adapter, chat2_store)` | Inject dependencies |
| `process_message` | `(self, *, primary_agent, account, message, conversation_id, context_name, secondary_agent, processor_factory) -> str` | Main entry: build prompt, run LLM loop, write chat2 events |
| `_build_context` | `(self, *, primary_agent, account, conversation_id, context_name) -> _ProcessorContext` | Extract and validate processor context from agent config |
| `_run_llm_loop` | `(self, *, ctx, prompt_messages, function_defs, primary_agent, secondary_agent, processor_factory, account, metrics) -> str` | Iterative LLM call loop with tool execution and duplicate detection |
| `_execute_tool_calls` | `(self, *, tool_calls, primary_agent, secondary_agent, processor_factory, account, ctx, metrics) -> List[Dict]` | Execute tool calls via registry, handle delegation |
| `_execute_simple_tasklist` | `(self, tasklist, *, supervisor_agent, worker_agent, account, conversation_id, context_name, processor_factory, delegation_depth) -> Dict` | Execute a tasklist inline (from `delegate_tasks` tool) |
| `_wrap_tool_calls` | `(self, tool_calls) -> List[_ToolCall]` | Convert raw tool call dicts to `_ToolCall` dataclasses |
| `_tool_calls_are_duplicate` | `(self, current, previous) -> bool` | Detect repeated identical tool calls |
| `_safe_json_loads` | `(self, s) -> Dict` | Safely parse JSON, return `{}` on failure |
| `_tool_result_to_text` | `(self, tool_result_text) -> str` | Serialize tool result, enforce size limit |
| `_get_environment_system_messages` | `(self) -> List[str]` | Read `environment_prompt_block` from config |
| `_ensure_chat2_session` | `(self, ctx) -> None` | Create chat2 session if missing |
| `_write_chat2_events` | `(self, ctx, user_message, assistant_response) -> None` | Write user + assistant events to chat2 |

## Methods — `AutomationProcessor`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, config, registry, storage, prompt_builder, chat2_store, llm_adapter)` | Inject dependencies |
| `process_message` | `(self, *, primary_agent, account, message, conversation_id, context_name, secondary_agent, processor_factory) -> str` | Parse JSON command, delegate to `execute_tasklist` |
| `execute_tasklist` | `(self, *, tasklist_id, mode, account_name, agent_name, conversation_id, context_name, primary_agent, account, secondary_agent, processor_factory) -> str` | Core execution loop: find pending tasks, execute via `FunctionCallingProcessor`, persist state |
| `_ensure_chat2_session` | `(self, conversation_id, account_name, agent_name) -> None` | Create chat2 session if missing |
| `_write_chat2_event` | `(self, conversation_id, account_name, agent_name, role, kind, payload, metadata) -> None` | Write a single event to chat2 with kind mapping |

## Methods — `TaskRunningProcessor`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, storage)` | Inject storage (optional) |
| `process_message` | `(self, *, primary_agent, account, message, conversation_id, context_name, secondary_agent, processor_factory) -> str` | Parse JSON command, find next pending task (no execution) |

## Methods — `ProcessorFactory`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, injector)` | Register processor name → import path mappings |
| `get` | `(self, processor_name)` | Lazy-import and construct processor via `Injector` |
