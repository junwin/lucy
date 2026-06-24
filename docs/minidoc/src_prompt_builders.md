---
tags:
  - src_prompt_builders
  - lucyproject
  - PromptBuilderInterface
  - PromptBuilder
  - build_prompt
  - chat_history
  - document_context
  - system_message
---

# src/prompt_builders — Module Overview

## Summary

Builds the full OpenAI-compatible messages array (prompt) for LLM model calls. Assembles system messages, chat history (from chat2 storage), named context text, relevant Obsidian document snippets, and the current user query into a single ordered list of message dicts.

## Key Classes

| Class | Description |
|---|---|
| `PromptBuilderInterface` (ABC) | Abstract base defining the `build_prompt()` contract |
| `PromptBuilder` | Concrete implementation with dependency injection via `@inject` |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Empty init |
| `prompt_builder_interface.py` | ABC with `build_prompt()` abstract method |
| `prompt_builder.py` | Full implementation: system message assembly, history loading, context/document injection, query finalisation |

## Dependencies

| Dependency | Usage |
|---|---|
| `src.config_manager.ConfigManager` | App configuration |
| `src.agent.AgentManager`, `Agent` | Agent lookup (system prompt, persona, style, max_conversations) |
| `src.storage.base.Storage` | Context state persistence (get/create context, document retrieval) |
| `src.chat2.facade.Chat2Store` | Chat2 session existence check and event streaming |
| `src.chat2.prompt_slice.get_last_n_events` | Select last N events from chat2 history |
| `src.utils.document_context.get_document_context` | Retrieve relevant Obsidian notes by query/tag |
| `injector` | Dependency injection decorator |
| `logging` | Structured logging of prompt composition |

## Methods — `PromptBuilderInterface` (ABC)

| Method | Signature | Description |
|---|---|---|
| `build_prompt` | `(self, *, content_text, conversation_id, agent_name, account_name, context_type, max_prompt_chars, context_name, extra_system_messages) -> List[ChatMessageDict]` | Abstract — build an OpenAI-compatible messages array |

## Methods — `PromptBuilder` (concrete)

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(self, agent_manager, config, storage, chat2_store=None)` | Injected constructor |
| `build_prompt` | `(self, *, content_text, conversation_id, agent_name, account_name, context_type, max_prompt_chars, context_name, extra_system_messages) -> List[Dict[str, str]]` | Full prompt assembly pipeline |
| `_build_agent_system_message` | `(self, agent_name, agent) -> str` | Combine system_prompt, persona, style_prompt |
| `_get_chat_history_messages` | `(self, conversation_id, account_name, agent_name, max_conversations) -> List[Dict[str, str]]` | Load history from chat2 store |
| `_get_context_state` | `(self, account_name, context_name) -> Optional[Any]` | Load/create ContextState from storage |
| `_get_context_text` | `(self, account_name, context_name) -> str` | Extract text from context state data dict |
| `_ensure_current_query` | `(self, messages, current_query) -> List[Dict[str, str]]` | Ensure last message is the current user query |
