---
tags:
  - FunctionCallingProcessor
  - ProcessorFactory
  - ToolResultTooLargeError
  - ToolHandlerError
  - MessageProcessorInterface
  - src.message_processors
  - message_processors
  - src.message_processors
  - messageprocessor
  - function calling
---

# src.message_processors

Short description: Message-processing pipeline for Lucy. Contains the core processors that turn incoming messages into model/tool calls, orchestrate guided conversations, and run automation task lists.

message processors Module - src/repos/lucy/src/message_processors
the relative path to FunctionCallingProcessor class is: `src/repos/lucy/src/message_processors/function_calling_processor.py`
the relative path to the MessageProcessorInterface class class is: `src/repos/lucy/src/message_processors/message_processor_interface.py`
the relative path to the ProcessorFactory class class is: `src/repos/lucy/src/message_processors/processor_factory.py`

- `src/message_processors/__init__.py`
  - (no classes)

- `src/message_processors/message_processor_interface.py`
  - `MessageProcessorInterface` – abstract base interface for all message processors, defining the `process_message` contract.

- `src/message_processors/function_calling_processor.py`
  - `FunctionCallingProcessor` – main tool-enabled processor that builds prompts, calls the model with function/tool definitions, executes tool calls via `HandlerRegistry`, and optionally executes `plan_tasks` tasklists.
  - `ToolResultTooLargeError` – raised when a tool result exceeds the configured size limit.
  - `ToolHandlerError` – raised when a tool handler fails during execution; propagated up to HTTP layer.

- `src/message_processors/processor_factory.py`
  - `ProcessorFactory` – maps `message_processor` names from agent config to concrete processor instances using dependency injection.

- `src/message_processors/types.py`
  - `AgentDict` – type alias for agent configuration dictionaries.
  - `AccountDict` – type alias for account dictionaries.
  - `OptionalAgentDict` – optional agent dict alias.
