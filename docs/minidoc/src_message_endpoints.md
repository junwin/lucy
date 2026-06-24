---
tags:
  - src_message_endpoints
  - lucyproject
  - AskRequestHandler
  - /ask
  - session_resolution
  - tasklist_autorun
---

# Module: `src.message_endpoints`

## Summary

The `src.message_endpoints` package provides the **HTTP request handling layer** for Lucy's `/ask` endpoint. It contains a single class, `AskRequestHandler`, which orchestrates the full lifecycle of an incoming chat request: payload validation, agent lookup, session resolution (by ID or friendly name), context creation, processor dispatch, and optional tasklist auto-execution via `TaskRunner`.

## Key Classes

| Class | Purpose |
|---|---|
| `AskRequestHandler` | Handles `/ask` requests — validates payload, resolves/creates sessions, dispatches to a message processor, and optionally auto-runs delegated tasklists. |

## Source Files

| File | Description |
|---|---|
| `ask_request_handler.py` | Single-file module containing `AskRequestHandler` class. No `__init__.py`. |

## Dependencies

- **Standard library**: `json`, `logging`, `typing`
- **Internal**:
  - `src.agent.AgentManager`, `src.agent.Agent`
  - `src.config_manager.ConfigManager`
  - `src.storage.base.Storage`
  - `src.storage.models.ChatMessage`
  - `src.message_processors.processor_factory.ProcessorFactory`
  - `src.message_processors.function_calling_processor.ToolHandlerError`
  - `src.chat2.facade.Chat2Store`

## Methods — `AskRequestHandler`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(agent_manager: AgentManager, config: ConfigManager, storage: Storage, processor_factory: ProcessorFactory, chat2_store: Optional[Chat2Store] = None) -> None` | Store dependencies for request handling. |
| `_maybe_autorun_tasklist` | instance | `(*, primary_agent: Agent, secondary_agent: Optional[Agent], account: Dict[str, Any], conversation_id: str, context_name: Optional[str], response_text: str) -> str` | If the processor response is a `delegate_tasks` tasklist JSON, execute it via `TaskRunner` and return the summary. |
| `handle` | instance | `(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]` | Process the `/ask` request: validate fields, resolve/create session, dispatch to processor, return response or error. |
