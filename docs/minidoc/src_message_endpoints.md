---
tags:
  - storage
  - module
  - askrequesthandler
  - agent_manager
  - agentmanager
  - config
  - configmanager
  - processor_factory
  - chat2_store
  - dict[str
  - src/message_endpoints
  - lucyproject
---

# Module: `src/message_endpoints`

## Source Files

| File | Description |
|------|-------------|
| `src/message_endpoints/ask_request_handler.py` | Single file — no `__init__.py` |

## Key Classes

### `AskRequestHandler`

Handles the `/ask` HTTP endpoint. Manages session resolution, delegates to a message processor, and optionally auto-runs tasklists via `TaskRunner`.

**Constructor:**

```python
def __init__(
    self,
    agent_manager: AgentManager,
    config: ConfigManager,
    storage: Storage,
    processor_factory: ProcessorFactory,
    chat2_store: Optional[Chat2Store] = None,
) -> None
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, agent_manager, config, storage, processor_factory, chat2_store=None) -> None` | Store dependencies |
| `_maybe_autorun_tasklist` | `(self, *, primary_agent, secondary_agent, account, conversation_id, context_name, response_text) -> str` | If the LLM returned a `delegate_tasks` tasklist, execute it via `TaskRunner` |
| `handle` | `(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]` | Process the `/ask` request — validate inputs, resolve/create session, call processor, return response |

## Dependencies

### Internal

| Module | Imported Names |
|--------|----------------|
| `src.agent` | `AgentManager`, `Agent` |
| `src.config_manager` | `ConfigManager` |
| `src.storage.base` | `Storage` |
| `src.message_processors.processor_factory` | `ProcessorFactory` |
| `src.message_processors.function_calling_processor` | `ToolHandlerError` |
| `src.storage.models` | `ChatMessage` |
| `src.chat2.facade` | `Chat2Store` |

### Standard Library

- `json`
- `logging`
- `typing` (`Any`, `Dict`, `Tuple`, `Optional`)
