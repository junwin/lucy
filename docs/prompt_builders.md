---
tags:
  - message
  - prompt_builder
  - str
  - prompt
  - system
  - prompt_builders
---

Module: prompt_builders

Purpose:
- Provides classes to build prompts for large language models. Central class is PromptBuilder, which composes system messages, historical context, document/context snippets, and the user prompt into a message array suitable for model calls. Integrates with AgentManager, ConfigManager, and Storage to fetch agent metadata, session history, and contextual data.

Key Classes:
- PromptBuilder (src/prompt_builders/prompt_builder.py): Builds the full prompt, combining agent/system prompts, chat history, external documents, and the current user content. Main service class in the module.
- PromptBuilderInterface (src/prompt_builders/prompt_builder_interface.py): Abstract interface declaring build_prompt.

Source Files:
- src/prompt_builders/prompt_builder.py
- src/prompt_builders/prompt_builder_interface.py
- (src/prompt_builders/__init__.py exists but is minimal)

Main Service / Base Class (PromptBuilder):
- __init__(self, agent_manager, config, storage): Injected dependencies.
- build_prompt(self, content_text, conversation_id, agent_name, account_name, context_type='none', max_prompt_chars=6000, context_name='', extra_system_messages=None) -> List[Dict[str, str]]
- _build_agent_system_message(self, agent_name, agent) -> str
- _get_chat_history_messages(self, conversation_id, account_name, agent_name, max_conversations) -> List[Dict[str, str]]
- _get_context_state(self, account_name, context_name) -> Optional[Any]
- _get_context_text(self, account_name, context_name) -> str
- _ensure_current_query(self, messages, current_query) -> List[Dict[str, str]]

Notes:
- The build_prompt flow includes: system message, optional extra system messages, chat history, context text, document contexts (if applicable), and the user message.
- Document context retrieval uses get_document_context to fetch relevant notes or snippets.
