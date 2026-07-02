---
tags:
  - src_message_processors
  - lucyproject
  - MessageProcessorInterface
  - ProcessorFactoryInterface
  - ProcessorFactory
  - FunctionCallingProcessor
  - AutomationProcessor
  - TaskRunningProcessor
  - _ProcessorContext
  - _ToolCall
  - ToolHandlerError
  - ToolResultTooLargeError
  - AgentDict
  - AccountDict
---

# src/message_processors

## 1. Summary

The `src/message_processors` module is the **orchestration layer** of the Lucy backend. It receives a user message, a configured agent, account metadata, and optional context, then produces a final response string. This is where tool-calling loops, task-list execution, and processor dispatch happen.

Its single responsibility: **turn a message into a response by routing through the correct processor, executing tools/LLM calls as needed, and storing results**.

It sits between the thin HTTP endpoint layer (`src/message_endpoints`) and the lower-level services (prompt building, tool handlers, LLM adapter, chat2 storage, task-list storage).

## 2. Architecture & Design

**Strategy pattern via factory**: Agent configs specify a `message_processor` string (e.g. `"function_calling_processor"`). `ProcessorFactory` maps these strings to processor classes, resolving them lazily via `importlib` and constructing them through the `Injector` DI container.

**Interface segregation**: `MessageProcessorInterface` defines the single `process_message()` contract. `ProcessorFactoryInterface` (a `Protocol`) defines the `get()` contract — no ABC inheritance required for factory consumers.

**Two-phase delegation** (AutomationProcessor): `process_message()` parses the inbound JSON command, validates it, writes a chat2 event, then delegates to `execute_tasklist()` for the actual execution loop. This split lets `execute_tasklist()` be called directly from tool handlers (e.g. `tasklists_run`) without re-parsing JSON.

**FCP layered loop** (FunctionCallingProcessor): `process_message()` builds context → filters allowed tools → calls `_run_llm_loop()` → writes chat2 events. The loop itself handles: LLM call → tool-call extraction → execution → output formatting → iteration until text response or limit hit.

**Ctx pattern** (frozen dataclass): `_ProcessorContext` and `_ToolCall` are frozen dataclasses used as lightweight value objects to pass parsed state through internal methods without long parameter lists.

**No legacy/v2 split** — all v1 storage references have been removed ("NO BACKWARD COMPATABILITY").

**Key design decisions**:
- Processors are constructed via `Injector`, never directly (`ProcessorFactory` docstring: _"processors must be constructed via Injector"_).
- `AutomationProcessor` relies on `FunctionCallingProcessor` obtained from the factory for actual task execution — creating a processor-within-processor pattern.
- `TaskRunningProcessor` is gated by agent name (`"doris"` only) and does not execute tasks — it only identifies the next pending task (Step 3.2 scaffold).
- `inject` decorator has a try/except shim for environments without the `injector` package (e.g. minimal test environments).

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `MessageProcessorInterface` | `ABC` | Abstract contract: `process_message()` |
| `ProcessorFactoryInterface` | `Protocol` | Structural contract: `get(processor_name)` |
| `ProcessorFactory` | `ABC` | Registry + lazy DI construction of processors |
| `FunctionCallingProcessor` | `MessageProcessorInterface` | Full tool-calling LLM loop (the main processor) |
| `AutomationProcessor` | `MessageProcessorInterface` | Executes persisted task-lists via FCP delegation |
| `TaskRunningProcessor` | `MessageProcessorInterface` | Scaffold: finds next pending task (agent="doris") |
| `_ProcessorContext` | frozen `dataclass` | Value object: parsed agent/config context |
| `_ToolCall` | frozen `dataclass` | Value object: parsed tool-call (name, id, args) |
| `ToolHandlerError` | `Exception` | Raised when a tool handler fails during execution |
| `ToolResultTooLargeError` | `Exception` | Raised when a tool result exceeds `max_tool_result_chars` |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Empty (no public re-exports) | — |
| `types.py` | Type aliases for agent/account dicts | `AgentDict`, `AccountDict`, `OptionalAgentDict` |
| `message_processor_interface.py` | Abstract contract for processors + factory Protocol | `MessageProcessorInterface`, `ProcessorFactoryInterface` |
| `processor_factory.py` | Name-to-class registry, lazy import, DI construction | `ProcessorFactory` |
| `function_calling_processor.py` | Main LLM + tool-calling processor | `FunctionCallingProcessor`, `ToolHandlerError`, `ToolResultTooLargeError`, `_ProcessorContext`, `_ToolCall` |
| `automation_processor.py` | Task-list execution processor | `AutomationProcessor` |
| `task_running_processor.py` | Scaffold: next-pending-task finder | `TaskRunningProcessor` |

## 5. Dependencies

### Standard library
`abc`, `dataclasses`, `importlib`, `json`, `logging`, `time`, `typing` (`Any`, `Dict`, `Iterable`, `List`, `Optional`, `Tuple`, `TYPE_CHECKING`), `datetime`

### Third-party packages
- `injector` — DI container (optional: shimmed when absent for test environments)

### Internal modules

| Consumer file | What it imports |
|---|---|
| `processor_factory` | `src.message_processors.function_calling_processor.FunctionCallingProcessor`, `src.message_processors.automation_processor.AutomationProcessor`, `src.message_processors.task_running_processor.TaskRunningProcessor` (all lazy via `importlib`) |
| `message_processor_interface` | `src.message_processors.types`, `src.agent.agent.Agent` |
| `function_calling_processor` | `src.config_manager`, `src.message_processors.message_processor_interface`, `src.prompt_builders.prompt_builder_interface`, `src.handlers.handler_registry`, `src.agent`, `src.llm.adapter_interface`, `src.chat2.facade`, `src.chat2.models` |
| `automation_processor` | `src.agent`, `src.config_manager`, `src.handlers.handler_registry`, `src.message_processors.message_processor_interface`, `src.prompt_builders.prompt_builder_interface`, `src.storage.base`, `src.storage.models`, `src.chat2.facade`, `src.chat2.models`, `src.tasklists.task`, `src.tasklists.task_list`, `src.tasklists.task_states`, `src.llm.adapter_interface` |
| `task_running_processor` | `src.message_processors.message_processor_interface`, `src.agent.agent`, `src.message_processors.types`, `src.storage.base`, `src.tasklists.task_states` |

### Optional dependencies
- `injector` — guarded by try/except in `automation_processor.py` and `function_calling_processor.py`
- `Chat2Store` — `Optional[Chat2Store]` in both FCP and AutomationProcessor; all calls guarded by `if self.chat2_store is None: return`
- `LLMAdapter` — `Optional[LLMAdapter]` in AutomationProcessor (needed for tool call output formatting)
- `Storage` — `Optional[Storage]` in TaskRunningProcessor constructor

## 6. Configuration / Settings

| Key | Type | Default | What it controls |
|---|---|---|---|
| `max_tool_result_chars` | int | `20000` | Maximum allowed length of a tool result string; results exceeding this raise `ToolResultTooLargeError` |
| `environment_prompt_block` | str | `""` | Optional multi-line string injected as an additional system message in the prompt (read by FCP via `_get_environment_system_messages()`) |

Additionally, these agent-level config fields are read at runtime (not from ConfigManager directly):

| Source | Field | Used by |
|---|---|---|
| Agent config | `model`, `temperature`, `context_type`, `max_function_call_iterations`, `save_responses`, `allowed_tools`, `delegation_depth`, `max_delegation_depth` | FCP |
| Account dict | `accountId` | All processors |
| Agent config | `name` | TaskRunningProcessor (gating), AutomationProcessor (logging) |

## 7. Exceptions

| Exception | Base | When Raised |
|---|---|---|
| `ToolHandlerError` | `Exception` | A tool handler raises an exception during `_execute_tool_calls`; also raised when the LLM returns tool_calls but no `response_id` |
| `ToolResultTooLargeError` | `Exception` | A tool result exceeds `max_tool_result_chars` after serialization |

## 8. Module-Level Constants

| Constant | Location | Value | Purpose |
|---|---|---|---|
| `_AUTOMATION_KIND_MAP` | `automation_processor.py` | `{"automation_command": "user_message", "task_completed": "system_note", "task_failed": "system_note", "automation_summary": "summary"}` | Maps automation-specific event kinds to valid `ChatEvent.kind` literal values |

Module-level helper functions (not classes):

| Function | File | Purpose |
|---|---|---|
| `_is_run_command(message)` | `automation_processor.py` | Detects whether a message is a task-list run command (JSON or free-text) |
| `_parse_execution_mode_from_text(message)` | `automation_processor.py` | Extracts `single-step` / `multi-step` from free-text |
| `_find_next_pending_task(tasklist)` | `automation_processor.py` | Finds next PENDING task in a `TaskList` object |
| `_set_task_state(task, state)` | `automation_processor.py` | Sets `task.state` |
| `_parse_json_command(message)` | `automation_processor.py` and `task_running_processor.py` | Parses a JSON command dict; returns `(dict, error)` |
| `_map_chat2_kind(kind)` | `automation_processor.py` | Maps automation kind → valid ChatEvent kind |
| `_safe_preview(text, limit)` | `automation_processor.py` | Truncates text for debug logging |
| `_now_utc()` | `automation_processor.py` | Returns `datetime.now(timezone.utc)` |
| `_find_next_pending_in_serialized(raw)` | `task_running_processor.py` | Finds next pending task in raw persisted representation (dict/list/JSON string) |

## 9. Methods (by class)

### MessageProcessorInterface

| Method | Type | Signature | Description |
|---|---|---|---|
| `process_message` | abstract instance | `(self, *, primary_agent: Agent, account: AccountDict, message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str` | Process a user message and return a response string. All parameters except `self` are keyword-only. `primary_agent`: the agent config. `account`: account dict (must contain `accountId`). `message`: raw user message (may be JSON or free-text depending on processor). `conversation_id`: session/thread identifier. `context_name`: named context for prompt building. `secondary_agent`: optional worker agent for delegation. `processor_factory`: optional factory for nested processor calls (e.g. FCP within AutomationProcessor). Returns the final response as a string. |

### ProcessorFactoryInterface (Protocol)

| Method | Type | Signature | Description |
|---|---|---|---|
| `get` | instance | `(self, processor_name: str) -> MessageProcessorInterface` | Return a constructed processor instance for the given name. Implementation is structural — any object with this method satisfies the protocol. |

### ProcessorFactory

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, injector: Injector)` | Stores the injector and builds the name→import-path registry. Registry maps `"function_calling_processor"`, `"automation_processor"`, and `"task_running_processor"` to their fully-qualified class paths. Decorated with `@inject`. |
| `get` | instance | `(self, processor_name: str) -> MessageProcessorInterface` | Normalizes `processor_name` (lowercase, strip), looks up the import path in `_registry`, lazy-imports the module, gets the class, and returns `self.injector.get(cls)`. Raises `ValueError` for unknown names. |

### FunctionCallingProcessor

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, config: ConfigManager, registry: HandlerRegistry, prompt_builder: PromptBuilderInterface, llm_adapter: LLMAdapter, chat2_store: Optional[Chat2Store] = None)` | Stores injected dependencies. `chat2_store` is optional; all chat2 operations are guarded. Decorated with `@inject`. |
| `process_message` | instance | `(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str` | Main entry point. Builds `_ProcessorContext`, validates `accountId`, loads environment system messages, builds prompt via `prompt_builder`, filters tool definitions by `allowed_tools`, runs the LLM loop, writes chat2 events if `store_this_call`, and returns the response. Re-raises `ToolHandlerError`; catches and logs all other exceptions then re-raises. Records performance metrics in `finally` block. |
| `_build_context` | instance | `(self, *, primary_agent: Agent, account: Dict[str, Any], conversation_id: str, context_name: str) -> _ProcessorContext` | Parses agent and account fields into a frozen `_ProcessorContext`. Clamps `max_iterations` to 1 if ≤ 0. |
| `_get_environment_system_messages` | instance | `(self) -> List[str]` | Reads `environment_prompt_block` from config. Returns `[]` if missing/empty; otherwise returns a single-element list with the stripped block. |
| `_run_llm_loop` | instance | `(self, *, ctx, prompt_messages, function_defs, primary_agent, secondary_agent, processor_factory, account, metrics) -> str` | Core loop: iterates up to `max_iterations`. Each iteration: calls `llm_adapter.call_model()`, extracts tool calls, detects duplicates (same name + same args as previous iteration → break with warning), executes tools via `_execute_tool_calls`, formats outputs for next input. If no tool calls, extracts text and breaks. Returns response text (or error message). |
| `_execute_tool_calls` | instance | `(self, *, tool_calls, primary_agent, secondary_agent, processor_factory, account, ctx, metrics) -> List[Dict[str, Any]]` | Iterates over tool calls: creates handler via `registry.create()`, calls `execute_raw()` if available (passing raw arguments string) or `execute()` otherwise (passing parsed JSON + handler_context), handles `delegate_tasks` specially (executes the returned tasklist via FCP delegation), enforces `max_tool_result_chars`, wraps each result via `llm_adapter.format_tool_output()`. Raises `ToolHandlerError` on handler failures; raises `ToolResultTooLargeError` on oversize results. |
| `_tool_calls_are_duplicate` | instance | `(self, current: List[_ToolCall], previous: List[_ToolCall]) -> bool` | Compares current tool calls to previous iteration's calls. Returns `True` if counts match and every (name, arguments_raw) pair is identical. Used for loop detection. |
| `_wrap_tool_calls` | instance | `(self, tool_calls: Iterable[Dict[str, Any]]) -> List[_ToolCall]` | Converts raw dict tool-calls from the LLM into `_ToolCall` frozen dataclasses. Defaults `arguments` to `"{}"` and `id` to `""`. |
| `_safe_json_loads` | instance | `(self, s: str) -> Dict[str, Any]` | Parses JSON safely: returns `{}` on empty, invalid, or non-dict JSON. Logs a warning for invalid JSON. |
| `_tool_result_to_text` | instance | `(self, tool_result_text: Any) -> str` | Normalizes a tool result to string (handles `None` → error JSON, non-string → JSON dump). Enforces `max_tool_result_chars` limit; raises `ToolResultTooLargeError` if exceeded. |
| `_ensure_chat2_session` | instance | `(self, ctx: _ProcessorContext) -> None` | Creates a chat2 session if one doesn't exist for `ctx.conversation_id`. Best-effort: logs and returns on failure. No-op if `chat2_store` is `None`. |
| `_write_chat2_events` | instance | `(self, ctx, user_message, assistant_response) -> None` | Writes user_message + assistant_message events to chat2. Best-effort: logs and returns on failure. |
| `_execute_simple_tasklist` | instance | `(self, tasklist, *, supervisor_agent, worker_agent, account, conversation_id, context_name, processor_factory, delegation_depth) -> Dict[str, Any]` | Executes a simple (non-persisted) tasklist from `delegate_tasks`. Enforces `max_delegation_depth`; refuses if exceeded. Iterates tasks: if agent matches worker, calls `self.process_message()` recursively; otherwise returns error. Returns summary dict with `ok` and `tasks` list. No chat2 events written (delegated execution). |

### AutomationProcessor

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, config: ConfigManager, registry: HandlerRegistry, storage: Storage, prompt_builder: PromptBuilderInterface, chat2_store: Optional[Chat2Store] = None, llm_adapter: Optional[LLMAdapter] = None)` | Stores injected dependencies. `chat2_store` and `llm_adapter` are optional. Decorated with `@inject`. |
| `process_message` | instance | `(self, *, primary_agent: Agent, account: Dict[str, Any], message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str` | Validates `context_name` (required), parses JSON command, validates `action` and `tasklist_id` and `mode`, writes `automation_command` chat2 event, then delegates to `execute_tasklist()`. Returns error strings for missing/unknown commands. |
| `execute_tasklist` | instance | `(self, *, tasklist_id, mode, account_name, agent_name, conversation_id, context_name, primary_agent, account, secondary_agent=None, processor_factory=None) -> str` | Core execution loop. Loads tasklist from storage, sets state to RUNNING, iterates pending tasks. For each: tries to obtain FCP from factory, builds task message from `general_instructions` + `task.instructions` + `task.meta`, executes via FCP, stores result/error on task, sets COMPLETED/FAILED state, persists after each task, writes chat2 event. In `single-step` mode stops after first task; in `multi-step` continues until no pending tasks or failure. Returns structured result string. |
| `_ensure_chat2_session` | instance | `(self, conversation_id, account_name, agent_name) -> None` | Creates a chat2 session if one doesn't exist. Best-effort: logs and returns on failure. |
| `_write_chat2_event` | instance | `(self, conversation_id, account_name, agent_name, role, kind, payload, metadata=None) -> None` | Writes a single chat2 event with automation kind mapping via `_map_chat2_kind()`. Preserves original kind in `metadata["automation_kind"]`. Best-effort. |

### TaskRunningProcessor

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, storage: Optional[Storage] = None) -> None` | Stores optional storage. Decorated with `@inject`. |
| `process_message` | instance | `(self, *, primary_agent: Agent, account: AccountDict, message: str, conversation_id: str = "0", context_name: str = "", secondary_agent: Optional[Agent] = None, processor_factory: Optional[Any] = None) -> str` | Gated by agent name: only responds if agent is `"doris"`. Parses JSON command, loads tasklist from storage, finds next PENDING task via `_find_next_pending_in_serialized`, returns task index and name. Does NOT execute tasks. Returns error strings for missing agent, context, storage, or tasklist. |

### _ProcessorContext (frozen dataclass)

No methods — value object with fields: `account_id`, `agent_name`, `conversation_id`, `context_name`, `model`, `temperature`, `context_type`, `max_iterations`, `store_this_call`, `delegation_depth`.

### _ToolCall (frozen dataclass)

No methods — value object with fields: `name`, `call_id`, `arguments_raw`.

## 10. Usage Examples

### Example 1: Processing a message through the factory (Flask route)

```python
from src.message_processors.processor_factory import ProcessorFactory

# Injected via DI
factory: ProcessorFactory

processor = factory.get("function_calling_processor")
response = processor.process_message(
    primary_agent=agent,
    account={"accountId": "junwin"},
    message="What is the weather?",
    conversation_id="session-123",
    context_name="lucyproject",
)
```

### Example 2: Running a persisted tasklist via AutomationProcessor

```python
import json
from src.message_processors.processor_factory import ProcessorFactory

factory: ProcessorFactory

processor = factory.get("automation_processor")
message = json.dumps({
    "action": "run",
    "tasklist_id": "my_tasks",
    "mode": "multi-step",
})
response = processor.process_message(
    primary_agent=agent,
    account={"accountId": "junwin"},
    message=message,
    conversation_id="session-456",
    context_name="lucyproject",
)
```

### Example 3: Direct LLM loop (minimal test setup)

```python
from src.message_processors.function_calling_processor import FunctionCallingProcessor

fcp = FunctionCallingProcessor(
    config=mock_config,
    registry=mock_registry,
    prompt_builder=mock_prompt_builder,
    llm_adapter=mock_llm_adapter,            # required
    chat2_store=None,                         # optional
)

response = fcp.process_message(
    primary_agent=mock_agent,
    account={"accountId": "test"},
    message="Hello",
    conversation_id="0",
)
```

## 11. Edge Cases & Gotchas

1. **Strict agent gating in TaskRunningProcessor**: Only responds when `agent_name == "doris"`. For all other agents it returns a "Not responsible" message. This is intentional scaffolding — the processor is not yet wired into production flows.

2. **AutomationProcessor requires context_name**: Despite not using `context_name` for tasklist access, `process_message()` requires it and returns an error if missing. This is a compatibility constraint from the interface.

3. **FCP metrics in `finally` block access potentially-unbound `ctx`**: The `finally` block uses `"ctx" in locals()` to check if `ctx` was assigned, because if `_build_context()` raises before assignment, `ctx` would be undefined.

4. **Duplicate tool-call detection**: If the LLM returns the exact same tool calls (same names + same arguments) on consecutive iterations, the FCP breaks the loop and returns a user-facing message. This prevents infinite loops but may abort legitimate retries if the model is simply being cautious.

5. **Tool calls without response_id**: If the LLM adapter returns tool calls but no `response_id`, `_execute_tool_calls` raises `ToolHandlerError`. This is a hard stop because function_call_output items cannot be chained without a previous response ID.

6. **Best-effort chat2 everywhere**: All `_ensure_chat2_session` and `_write_chat2_event` methods swallow exceptions. Chat2 failures never propagate — they are logged and discarded. This means session/event loss can happen silently.

7. **`_execute_simple_tasklist` does NOT write chat2**: Unlike the main FCP loop, the delegated tasklist execution from `delegate_tasks` does not record chat2 events for individual task interactions. Only the final summary is returned to the caller.

8. **AutomationProcessor storage persistence on EVERY task**: Persists to storage after setting RUNNING state, after each task's COMPLETED/FAILED state, and for the final tasklist state. On persist failure, sets the tasklist state to FAILED and returns immediately — remaining tasks are abandoned.

9. **Task message assembly priority**: `general_instructions` (tasklist-level) → `task.instructions` → `task.meta` fields. If no instructions at all, the task is marked COMPLETED with a warning; it does not fail.

10. **inject shim alters behavior in test environments**: Both `automation_processor.py` and `function_calling_processor.py` have a try/except around `from injector import inject` that defines a no-op `inject` fallback. In test environments without `injector`, `@inject` does nothing, which means constructors are called with whatever arguments the test provides — no automatic DI.

11. **ProcessorFactory lazy imports may fail at runtime**: The factory defers imports to `get()` time. If a processor class is moved, renamed, or its module has import errors, the failure happens during message processing, not at startup.

12. **`allowed_tools` strict intersection**: If `allowed_tools` is `None` or `[]`, NO tools are passed to the LLM at all. Unknown tool names in `allowed_tools` are logged as warnings and silently dropped. There is no error for this misconfiguration.

13. **Cross-processor circular import risk**: The `ProcessorFactory` docstring explicitly warns about circular imports. `AutomationProcessor` → `ProcessorFactory` → `FunctionCallingProcessor` → handler registry can form a cycle. The lazy import pattern in `ProcessorFactory` breaks this.

14. **Broad except in AutomationProcessor task execution**: `except Exception` catches all errors during FCP task execution and marks the task as FAILED. This includes `SystemExit` and `KeyboardInterrupt` (though unlikely in a web server context).

15. **`delegation_depth` propagation in _execute_simple_tasklist**: Depth is incremented only for recursive `process_message()` calls within `_execute_simple_tasklist`. The main FCP loop itself does NOT increment delegation depth — `_ProcessorContext.delegation_depth` is set once from `primary_agent.delegation_depth` at the start.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/message_endpoints/ask_request_handler.py` | `ProcessorFactory` (constructs processor via factory), `ToolHandlerError` (caught in except clause) |
| `src/container_config.py` | `ProcessorFactoryInterface` (for DI binding), `ProcessorFactory` (registered as implementation) |
| `src/handlers/tasklists_run_handler.py` | `AutomationProcessor` (calls `execute_tasklist()` directly) |
| `app.py` | Indirect via `AskRequestHandler` → `ProcessorFactory` |
| `main.py` | Indirect via `AskRequestHandler` → `ProcessorFactory` |
| `tests/conftest.py` | `FunctionCallingProcessor` (instantiated in fixture setup) |
| `tests/test_function_calling_processor.py` | `ToolHandlerError` (imported for exception testing) |
