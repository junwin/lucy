---
tags:
  - list_context_names_impl
  - list_tasklists_impl
  - get_tasklist_impl
  - put_tasklist_impl
  - search_documents_impl
  - endpoint
  - get_agents_impl
  - delete_tasklist_impl
  - get_chats_impl
  - get_chat_impl
  - src/http_endpoints
  - lucyproject
---

# Module: `src/http_endpoints`

HTTP endpoint implementations for the Lucy API. Each file contains standalone
functions (no classes) that implement the business logic for a set of related
HTTP routes. All functions return `(body, status_code)` tuples.

## Source Files (7)

| File | Functions |
|------|-----------|
| `agents_endpoints.py` | `get_agents_impl`, `list_context_names_impl`, `list_tasklists_impl`, `get_tasklist_impl`, `put_tasklist_impl`, `delete_tasklist_impl` |
| `chats_endpoints.py` | `post_chat_impl`, `get_chats_impl`, `get_chat_impl`, `post_chat_message_impl`, `delete_chat_impl`, `update_chat_impl`, `_chat2_session_to_response` |
| `context_endpoints.py` | `list_context_names_impl` |
| `documents_endpoints.py` | `search_documents_impl` |
| `prompt_and_docs_endpoints.py` | `build_prompt_impl`, `search_documents_impl` |
| `prompt_builder_endpoints.py` | `build_prompt_impl` |
| `tasklist_endpoints.py` | `list_tasklists_impl`, `get_tasklist_impl`, `put_tasklist_impl`, `delete_tasklist_impl` |

## Key Classes

None. All functions are standalone — no classes, no base class, no service class.
No `__init__.py` exists in the package.

## Dependencies

### Internal Consumers
- `app.py` — imports all endpoint functions and wires them to Flask routes

### Internal Dependencies
- `src.chat2.facade.Chat2Store` — chat session storage (chats_endpoints)
- `src.chat2.models.ChatEvent` — event model (chats_endpoints)
- `src.agent.AgentManager` — agent validation and lookup
- `src.prompt_builders.prompt_builder.PromptBuilder` — prompt construction

### External Dependencies
- `logging` — error logging
- `typing` — `Any`, `Dict`, `List`, `Optional`, `Tuple`

## Key Functions

### Agents & Context
- `get_agents_impl(agent_manager)` — list all available agents
- `list_context_names_impl(storage, account_name)` — list context names for an account

### Chats (chat2-backed, Phase 4)
- `post_chat_impl(chat2_store, agent_manager, payload)` — create a new chat session
- `get_chats_impl(chat2_store, agent_manager, agent_name, account_name, limit)` — list sessions
- `get_chat_impl(chat2_store, session_id)` — get session + events
- `post_chat_message_impl(chat2_store, session_id, data)` — append a message event
- `delete_chat_impl(chat2_store, session_id)` — delete a session
- `update_chat_impl(chat2_store, session_id, payload)` — update friendly_name, tags, metadata

### Documents
- `search_documents_impl(storage, data)` — poor-man's document search

### Prompt Building
- `build_prompt_impl(agent_manager, storage, container, config, payload)` — build a prompt with context

### Tasklists
- `list_tasklists_impl(storage, account_name)` — list tasklist IDs
- `get_tasklist_impl(storage, account_name, tasklist_name)` — get a tasklist
- `put_tasklist_impl(storage, account_name, tasklist_name, payload)` — save a tasklist
- `delete_tasklist_impl(storage, account_name, tasklist_name)` — delete a tasklist
