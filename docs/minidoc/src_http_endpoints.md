---
tags:
  - src_http_endpoints
  - lucyproject
  - get_agents_impl
  - post_chat_impl
  - get_chat_impl
  - get_chats_impl
  - build_prompt_impl
  - search_documents_impl
  - list_tasklists_impl
  - prompt_builder_debug_impl
  - endpoint
  - chat2
---

# Module: `src.http_endpoints`

## Summary

HTTP endpoint implementation layer for the Lucy API. Each file contains standalone functions (no classes) that implement the business logic for a set of related HTTP routes. All functions return `(body, status_code)` tuples consumed by Flask route handlers in `app.py`. The module is chat2-backed for chat operations (Phase 4) and uses v1 `Storage` for documents, contexts, and tasklists.

## Key Classes

None. All functions are standalone — no classes, no base class, no service class. No `__init__.py` exists in the package.

## Source Files

| File | Description |
|---|---|
| `agents_endpoints.py` | Agent listing, context name listing, tasklist CRUD (legacy duplicates) |
| `chats_endpoints.py` | Chat session CRUD — create, list, get, update, delete, append messages (chat2-backed) |
| `context_endpoints.py` | Context name listing for an account |
| `documents_endpoints.py` | Document search via poor-man's keyword matching |
| `prompt_and_docs_endpoints.py` | Prompt building + document search (combined legacy endpoint) |
| `prompt_builder_endpoints.py` | Prompt building with context injection |
| `prompt_builder_debug_endpoints.py` | Diagnostic endpoint — traces document loading pipeline |
| `tasklist_endpoints.py` | Tasklist CRUD — list, get, put, delete |

## Dependencies

### Internal Consumers
- `app.py` — imports all endpoint functions and wires them to Flask routes

### Internal Dependencies
- `src.chat2.facade.Chat2Store` — chat session storage (chats_endpoints)
- `src.chat2.models.ChatEvent` — event model for message appending
- `src.agent.AgentManager` — agent validation and lookup
- `src.prompt_builders.prompt_builder.PromptBuilder` — prompt construction
- `src.config_manager.ConfigManager` — config access (debug endpoint)
- `src.storage.base.Storage` — document/context/tasklist storage
- `src.utils.document_context.get_document_context` — document retrieval (debug)
- `src.utils.text_snippet_loader.load_text_snippet` — snippet loading (debug)
- `src.keywords.keywords.Keywords` — keyword extraction (debug)

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
- `get_chat_impl(chat2_store, session_id)` — get session metadata + all events
- `post_chat_message_impl(chat2_store, session_id, data)` — append a user/assistant message event
- `delete_chat_impl(chat2_store, session_id)` — delete a session and its events
- `update_chat_impl(chat2_store, session_id, payload)` — update friendly_name, tags, metadata
- `_chat2_session_to_response(meta, events)` — helper: convert ChatSessionMeta to response dict

### Documents
- `search_documents_impl(storage, data)` — poor-man's keyword-based document search

### Prompt Building
- `build_prompt_impl(agent_manager, storage, container, config, payload)` — build a prompt with document context and conversation history
- `prompt_builder_debug_impl(storage, config, payload)` — diagnostic: trace keyword extraction, document scoring, and snippet selection

### Tasklists
- `list_tasklists_impl(storage, account_name)` — list tasklist IDs
- `get_tasklist_impl(storage, account_name, tasklist_name)` — get a tasklist by name
- `put_tasklist_impl(storage, account_name, tasklist_name, payload)` — save/update a tasklist
- `delete_tasklist_impl(storage, account_name, tasklist_name)` — delete a tasklist
