---
title: "src/message_processors"
tags:
  - src/message_processors
  - message_processor
  - message_processors
  - processor
  - messageprocessorinterface
  - base
  - injector
  - functioncallingprocessor
  - message
  - json
  - str
  - doc
  - source
---

# `src/message_processors`

## Source files (focus folder)
- `src/message_processors/__init__.py`
- `src/message_processors/types.py`
- `src/message_processors/message_processor_interface.py`
- `src/message_processors/processor_factory.py`
- `src/message_processors/function_calling_processor.py`
- `src/message_processors/automation_processor.py`
- `src/message_processors/task_running_processor.py`

## Key classes
- **`MessageProcessorInterface`** (`message_processor_interface.py`)
  - Abstract base for all message processors.
  - Defines the common entrypoint: `process_message(...) -> str`.

- **`ProcessorFactory`** (`processor_factory.py`)
  - Maps agent config `message_processor` names to concrete processor classes.
  - Uses **Injector** to construct processors (keeps imports lazy to avoid circular imports).

- **`FunctionCallingProcessor`** (`function_calling_processor.py`)
  - Main “tool calling” processor.
  - Builds prompt via `PromptBuilderInterface`.
  - Gets tool definitions from `HandlerRegistry`, then filters by `agent.allowed_tools`.
  - Runs an LLM loop via `LLMAdapter`:
    - extracts tool calls
    - executes handlers
    - sends `function_call_output` items back to the model
  - Optionally stores user/assistant messages to `Storage`.

- **`AutomationProcessor`** (`automation_processor.py`)
  - Runs persisted `TaskList` objects from `Storage`.
  - Updates task/tasklist state and persists checkpoints.
  - Can delegate each task execution to `FunctionCallingProcessor` (via `ProcessorFactory`).

- **`TaskRunningProcessor`** (`task_running_processor.py`)
  - Parses a JSON “run tasklist” command.
  - Loads a tasklist from `Storage` and finds the next `Pending` task.
  - Does **not** execute tasks (selection only).

## Dependencies
### Standard library
- `abc`, `dataclasses`, `importlib`, `json`, `logging`, `time`, `datetime`, `typing`

### Third-party
- `injector`
  - Note: some modules include a small shim if `injector` is missing.

### Internal
- Agents/config:
  - `src.agent.Agent`
  - `src.config_manager.ConfigManager`
- Tools:
  - `src.handlers.handler_registry.HandlerRegistry`
- Prompting/LLM:
  - `src.prompt_builders.prompt_builder_interface.PromptBuilderInterface`
  - `src.llm.adapter_interface.LLMAdapter`
- Storage:
  - `src.storage.base.Storage`
  - `src.storage.models.ChatMessage`
- Tasklists:
  - `src.tasklists.task_list.TaskList`, `src.tasklists.task.Task`, `src.tasklists.task_states.*`

## Methods in the module service/base class
### `MessageProcessorInterface` (base)
- `process_message(self, *, primary_agent, account, message, conversation_id="0", context_name="", secondary_agent=None, processor_factory=None) -> str`

### `ProcessorFactory` (service)
- `__init__(self, injector: Injector)`
- `get(self, processor_name: str) -> MessageProcessorInterface`

## Keywords (from get_keywords)
- message_processor
- message_processors
- processor
- messageprocessorinterface
- base
- injector
- functioncallingprocessor
- message
- json
- str
- doc
- source
