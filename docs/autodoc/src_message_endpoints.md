---
tags:
  - agent
  - askrequesthandler
  - config
  - dict[str
  - doc
  - message_endpoint
  - source
  - message_endpoints
  - endpoint
  - request
  - src/message_endpoints
---

# `src/message_endpoints`

## Overview
This module contains request-handler code for HTTP message endpoints. Currently it provides the handler for the **`/ask`** endpoint.

## Source files
- `src/message_endpoints/ask_request_handler.py`

## Key classes
### `AskRequestHandler` (`src/message_endpoints/ask_request_handler.py`)
Handles the `/ask` endpoint.

Responsibilities:
- Parse and validate request payload fields (`question`, `agentName`, `accountName`, optional context/session fields)
- Validate agent name and load agent configuration via `AgentManager`
- Ensure a storage context exists when `contextName` is provided (`storage.get_or_create_context` if available)
- Resolve or create a chat session when `conversationId` is missing (optionally using `friendlyName`)
- Select the configured message processor via `ProcessorFactory` and call `processor.process_message(...)`
- Convert tool execution failures (`ToolHandlerError`) into a 500 response and append an error message to the chat session

## Dependencies
### Standard library
- `json`
- `logging`
- `typing` (`Any`, `Dict`, `Tuple`, `Optional`)

### Internal
- `src.agent` (`AgentManager`, `Agent`)
- `src.config_manager.ConfigManager`
- `src.storage.base.Storage`
- `src.message_processors.processor_factory.ProcessorFactory`
- `src.message_processors.function_calling_processor.ToolHandlerError`
- `src.storage.models.ChatMessage`

## Methods (service/base class)
### `AskRequestHandler`
- `__init__(agent_manager: AgentManager, config: ConfigManager, storage: Storage, processor_factory: ProcessorFactory) -> None`
- `_maybe_autorun_tasklist(*, primary_agent: Agent, secondary_agent: Optional[Agent], account: Dict[str, Any], conversation_id: str, context_name: Optional[str], response_text: str) -> str`
- `handle(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]`
