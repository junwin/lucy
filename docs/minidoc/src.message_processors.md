---
tags:
  - GuidedConversationProcessor
  - FunctionCallingProcessor
  - ProcessorFactory
  - ToolResultTooLargeError
  - ToolHandlerError
  - AutomationProcessor
  - MessageProcessorInterface
  - src.message_processors
  - message_processors
  - src.message_processors
---

# src.message_processors

Short description: Message-processing pipeline for Lucy. Contains the core processors that turn incoming messages into model/tool calls, orchestrate guided conversations, and run automation task lists.

## Python files and key classes

- `src/message_processors/__init__.py`
  - (no classes)

- `src/message_processors/message_processor_interface.py`
  - `MessageProcessorInterface` – abstract base interface for all message processors, defining the `process_message` contract.

- `src/message_processors/guided_conversation_processor.py`
  - `GuidedConversationProcessor` – orchestrates a guided conversation between a primary agent and an SME/coach agent, managing shared context and injecting SME guidance into the primary agent’s system messages.

- `src/message_processors/function_calling_processor.py`
  - `FunctionCallingProcessor` – main tool-enabled processor that builds prompts, calls the model with function/tool definitions, executes tool calls via `HandlerRegistry`, and optionally executes `plan_tasks` tasklists.
  - `ToolResultTooLargeError` – raised when a tool result exceeds the configured size limit.
  - `ToolHandlerError` – raised when a tool handler fails during execution; propagated up to HTTP layer.

- `src/message_processors/automation_processor.py`
  - `AutomationProcessor` – processor for running simple automation task lists (currently focused on supervisor agent `doris`), delegating work to a worker agent and updating task states.

- `src/message_processors/processor_factory.py`
  - `ProcessorFactory` – maps `message_processor` names from agent config to concrete processor instances using dependency injection.

- `src/message_processors/types.py`
  - `AgentDict` – type alias for agent configuration dictionaries.
  - `AccountDict` – type alias for account dictionaries.
  - `OptionalAgentDict` – optional agent dict alias.
