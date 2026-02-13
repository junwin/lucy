---
tags:
  - agent
  - json
  - str
  - configuration
  - loading
  - entry
  - bool
  - to_dict
  - agentmanager
  - definition
  - src/agent
---

# `src/agent`

## Purpose
Agent configuration model and manager for loading/saving agent definitions.

## Summary (short)
- Defines the `Agent` config model (validation + legacy field mapping).
- Provides `AgentManager` to load/save agents from JSON and query them by name.

## Source files
- `src/agent/agent.py`
- `src/agent/agent_manager.py`
- `src/agent/__init__.py`

## Key classes
### `Agent` (`src/agent/agent.py`)
Dataclass representing an agent configuration.

Responsibilities:
- Legacy field mapping:
  - `select_type` → `context_type`
  - `save_reposnses` → `save_responses`
- Validation: unknown fields hard-fail that agent entry (so typos are caught)
- Type coercion/validation:
  - `allowed_tools`: `None` | `list[str]` | comma-separated `str`
  - ints: `max_prompt_conversations`, `max_prompt_documents`, `max_function_call_iterations`
  - `temperature`: float
  - `save_responses`: bool
- Serialization: `to_dict()`

Key methods:
- `from_dict(data: dict) -> Agent`
- `to_dict() -> dict`

### `AgentManager` (`src/agent/agent_manager.py`)
Service class that manages a collection of `Agent` objects stored in JSON.

Responsibilities:
- Load agents from a JSON file (default `./agents.json`)
- Robust loading: malformed agent entries are logged and skipped
- Accepts JSON as either a list of agents or a single agent object

Methods (service/base class):
- `__init__(path: str = "./agents.json")`
- `load_agents() -> None`
- `save_agents() -> None`
- `get_agent(name: str) -> Agent | None`
- `is_valid(name: str) -> bool`
- `get_agent_names() -> list[str]`
- `get_available_agents() -> list[Agent]`
- `upsert_agent(agent: Agent) -> None`

## Dependencies
- Standard library: `dataclasses`, `typing`, `logging`, `json`, `pathlib`
- Internal:
  - `src.agent.agent.Agent` (used by `AgentManager`)
---
tags:
  - handler
  - base
  - handlerregistry
  - doc
  - source
  - handlerv2
  - register
  - def
  - schemahandlerv2
  - resultenvelope
  - src/handlers
---

# `src/handlers`

## Purpose
Tool/handler layer. Defines the `HandlerV2` contract, a `HandlerRegistry` to register and instantiate handlers, and concrete handler implementations for file IO, command execution, web scraping/search, keywords, planning, and tasklist management.

## Summary (short)
- Central place where “tools” are defined and executed.
- `HandlerRegistry` exposes tool schemas to the LLM and instantiates handlers by name.

## Source files
- `src/handlers/__init__.py`
- `src/handlers/command_execution_handler2.py`
- `src/handlers/file_load_handler2.py`
- `src/handlers/file_save_handler.py`
- `src/handlers/get_keywords_handler.py`
- `src/handlers/handler.py`
- `src/handlers/handler_registry.py`
- `src/handlers/handler_utils.py`
- `src/handlers/handler_v2.py`
- `src/handlers/plan_tasks_handler.py`
- `src/handlers/registry_bootstrap.py`
- `src/handlers/schema_handler_v2.py`
- `src/handlers/scrape_web_page_handler2.py`
- `src/handlers/tasklists_manage_handler.py`
- `src/handlers/web_search_handler2.py`

## Key classes
- **`HandlerV2`** (`handler_v2.py`): abstract base class for tool handlers.
- **`HandlerRegistry`** (`handler_registry.py`): registers handler classes by tool name, exposes tool definitions, instantiates handlers, and caches result schemas.
- **`SchemaHandlerV2`**, **`ResultEnvelope`**, **`ErrorCode`** (`schema_handler_v2.py`): schema/result envelope helpers (Pydantic-based).
- Concrete `HandlerV2` implementations:
  - `FileLoadHandler2`, `FileSaveHandler2`
  - `CommandExecutionHandler2`
  - `ScrapeWebPageHandler2`, `WebSearchHandler2`
  - `GetKeywordsHandler`
  - `PlanTasksHandler`, `TasklistsManageHandler`

## Dependencies
- **stdlib:** `abc`, `enum`, `json`, `logging`, `os`, `re`, `shlex`, `subprocess`, `typing`
- **third-party:** `pydantic` (schemas), `requests` (web search)
- **internal:**
  - `src.config_manager.ConfigManager`
  - `src.keywords.keywords.Keywords`
  - `src.storage.json_file_storage.JsonFileStorage`
  - `src.storage_paths.storage_paths.StoragePaths`
  - `src.tasklists.task_list.TaskList`

## Methods in the module service/base class
### `HandlerRegistry` (`handler_registry.py`)
- `__init__(self) -> None`
- `register(self, handler_cls: Type[HandlerV2]) -> None`
- `create(self, name: str, *, config: Any) -> HandlerV2`
- `tools(self) -> List[Dict[str, Any]]`
- `tool_names(self) -> List[str]`
- `result_schema(self, name: str) -> Optional[Dict[str, Any]]`
- `all_result_schemas(self) -> Dict[str, Dict[str, Any]]`

### Bootstrap
- `build_registry() -> HandlerRegistry` (`registry_bootstrap.py`): registers core handlers and returns a ready-to-use registry.

## Keywords (from `get_keywords`)
`handler`, `base`, `handlerregistry`, `doc`, `source`, `handlerv2`, `register`, `def`, `schemahandlerv2`, `resultenvelope`
---
tags:
  - str
  - keyword
  - set
  - module
  - top_n
  - int
  - float
  - doc
  - source
  - extraction
  - src/keywords
---

# `src/keywords`

## Source files
- `src/keywords/keywords.py`

## Summary (short)
- Extracts keywords from text (spaCy + NLTK) and provides simple semantic similarity helpers.

## Key classes
- **`Keywords`** (`src/keywords/keywords.py`)
  - Extracts keywords from text using spaCy (POS + lemmatization) and frequency counting.
  - Supports a “request keywords:” escape hatch to accept explicitly provided keywords.
  - Provides semantic similarity helpers (TF‑IDF cosine similarity when sklearn is available; otherwise a lightweight fallback).

## Dependencies
- **stdlib**: `typing` (`List`, `Dict`, `Set`), `collections.Counter`, `datetime`, `re`
- **third-party**:
  - **NLTK**: `nltk`, `nltk.tokenize.word_tokenize`, `nltk.stem.SnowballStemmer`, `nltk.corpus.wordnet`
  - **spaCy** (lazy import in `_initialize_nlp_model`): loads `en_core_web_sm` or `es_core_news_sm`; uses spaCy `STOP_WORDS`
  - **scikit-learn** (optional): `TfidfVectorizer`, `cosine_similarity` (preferred implementation)

## Main service/base class: `Keywords`

### Methods
- `__init__(language_code: str = "en")`
- `_initialize_nlp_model()`
- `extract_from_content(content: str, top_n: int = 10) -> List[str]`
- `extract_keywords(content: str, top_n: int = 10) -> List[str]`
- `get_specified_keywords(input_str: str) -> List[str]`
- `compare_keyword_lists_semantic_similarity(keywords1: List[str], keywords2: List[str]) -> float`
- `compare_semantic_similarity(text1: str, text2: List[str]) -> float`
- `compare_keywords(set1: set, set2: set, operator: str = "and") -> bool`
- `concatenate_keywords(keyword_list: List[str]) -> str`

## Other module-level items
- `ensure_nltk_data(*, logger=None) -> None` (auto-downloads required NLTK datasets, currently `punkt`)
- Constants/regex:
  - `DEFAULT_CUSTOM_EXCLUDE`, `STOP_WORDS`
  - `CODELIKE_RE` (paths/filenames), `SYMBOL_RE` (symbol-only tokens)
---
tags:
  - llm
  - protocol
  - llmresponse
  - openai
  - dataclasse
  - temperature
  - tool_choice
  - store
  - metadata
  - previous_response_id
  - src/llm
---

# `src/llm`

## Purpose
LLM abstraction layer. Defines a normalized interface (`LLMApi`) and adapter contract (`LLMAdapter`) so the rest of the codebase (e.g., the FunctionCallingProcessor) can stay mostly LLM-provider agnostic.

## Summary (short)
- Normalizes LLM calls and tool-calling across providers.
- Current concrete implementation targets OpenAI Responses API.

## Source files
- `src/llm/__init__.py` (exports public API; optional OpenAI imports)
- `src/llm/interface.py` (`LLMApi` protocol)
- `src/llm/adapter_interface.py` (`LLMAdapter` protocol)
- `src/llm/dto.py` (normalized DTOs: `ToolCall`, `LLMUsage`, `LLMResponse`)
- `src/llm/openai_responses_adapter.py` (`OpenAIResponsesAdapter`)
- `src/llm/openai_responses.py` (`OpenAIResponsesApi` + extraction helpers)

## Key classes / protocols
- **`LLMApi`** (`src/llm/interface.py`)
- **`LLMAdapter`** (`src/llm/adapter_interface.py`)
- **DTOs** (`src/llm/dto.py`): `ToolCall`, `LLMUsage`, `LLMResponse`
- **`OpenAIResponsesAdapter`** (`src/llm/openai_responses_adapter.py`)
- **`OpenAIResponsesApi`** (`src/llm/openai_responses.py`)

## Dependencies
- **stdlib:** `typing`, `dataclasses`, `json`, `logging`, `os`, `random`, `time`
- **third-party:** `openai` (optional; module provides lightweight fallbacks when not installed)
- **internal:** `src.config_manager.ConfigManager`

## Methods in the module service/base class
### `LLMApi` (service interface)
- `create_response(*, model, input, temperature=None, tools=None, tool_choice=None, store=None, metadata=None, previous_response_id=None, text=None) -> LLMResponse`

### `LLMAdapter` (adapter interface)
- `call_model(*, model, input, temperature=None, tools=None, tool_choice=None, store=None, metadata=None, previous_response_id=None, text=None) -> Any`
- `extract_tool_calls(response) -> list[dict]`
- `format_tool_output(*, call_id, output) -> dict`
- `get_text(response) -> str`
- `get_response_id(response) -> str | None`
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

## Summary (short)
- HTTP boundary for `/ask`: validates payload, resolves agent/session/context, then delegates to a message processor.

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

## Summary (short)
- Message processing layer: routes a user message through either tool-calling chat (`FunctionCallingProcessor`) or tasklist automation (`AutomationProcessor`).

## Key classes
- **`MessageProcessorInterface`** (`message_processor_interface.py`)
- **`ProcessorFactory`** (`processor_factory.py`)
- **`FunctionCallingProcessor`** (`function_calling_processor.py`)
- **`AutomationProcessor`** (`automation_processor.py`)
- **`TaskRunningProcessor`** (`task_running_processor.py`)

## Dependencies
### Standard library
- `abc`, `dataclasses`, `importlib`, `json`, `logging`, `time`, `datetime`, `typing`

### Third-party
- `injector`

### Internal
- Agents/config: `src.agent.Agent`, `src.config_manager.ConfigManager`
- Tools: `src.handlers.handler_registry.HandlerRegistry`
- Prompting/LLM: `src.prompt_builders.prompt_builder_interface.PromptBuilderInterface`, `src.llm.adapter_interface.LLMAdapter`
- Storage: `src.storage.base.Storage`, `src.storage.models.ChatMessage`
- Tasklists: `src.tasklists.task_list.TaskList`, `src.tasklists.task.Task`, `src.tasklists.task_states.*`

## Methods in the module service/base class
### `MessageProcessorInterface` (base)
- `process_message(self, *, primary_agent, account, message, conversation_id="0", context_name="", secondary_agent=None, processor_factory=None) -> str`

### `ProcessorFactory` (service)
- `__init__(self, injector: Injector)`
- `get(self, processor_name: str) -> MessageProcessorInterface`
---
tags:
  - message
  - prompt_builder
  - module
  - base
  - system
  - agent
  - config
  - document
  - context_name
  - doc
  - src/prompt_builders
---

# `src/prompt_builders`

## Source files
- `src/prompt_builders/__init__.py`
- `src/prompt_builders/prompt_builder_interface.py`
- `src/prompt_builders/prompt_builder.py`

## Summary (short)
- Builds the LLM prompt (system + history + optional context/doc snippets + current user message).

## Key classes
- **`PromptBuilderInterface`** (`prompt_builder_interface.py`)
- **`PromptBuilder`** (`prompt_builder.py`)

## Dependencies
- **stdlib:** `abc`, `logging`, `typing`
- **third-party:** `injector`
- **internal:** `src.config_manager.ConfigManager`, `src.agent.AgentManager`, `src.storage.base.Storage`, `src.utils.document_context.get_document_context`

## Methods in the module service/base class
### `PromptBuilderInterface`
- `build_prompt(*, content_text, conversation_id, agent_name, account_name, context_type="none", max_prompt_chars=6000, context_name="", extra_system_messages=None) -> List[ChatMessageDict]`
---
tags:
  - storage
  - contextstate
  - friendly_name
  - tag
  - json
  - chatmessage
  - chatsession
  - embeddingrecord
  - agent_name
  - context_id
  - doc
  - source
  - src/storage
---

# `src/storage`

## Source files
- `src/storage/__init__.py`
- `src/storage/base.py`
- `src/storage/json_file_storage.py`
- `src/storage/models.py`

## Summary (short)
- Storage abstraction + JSON/Markdown file-backed implementation for chats, contexts, documents, and tasklists.

## Key classes
- **`Storage`** (`src/storage/base.py`): abstract storage interface for Lucy.
- **`JsonFileStorage`** (`src/storage/json_file_storage.py`): JSON/Markdown file-backed implementation of `Storage`.
- **Storage data models** (`src/storage/models.py`): `ChatMessage`, `ChatSession`, `ContextState`, `DocumentRef`, etc.

## Dependencies
- **stdlib:** `abc`, `dataclasses`, `datetime`, `json`, `logging`, `os`, `pathlib`, `re`, `typing`, `uuid`
- **third-party:** `yaml` (PyYAML)
- **internal:** `src.tasklists`, `src.storage_paths.storage_paths.StoragePaths`, `src.keywords.keywords.Keywords`

## Methods in the module service/base class
### `Storage` (abstract)
- `create_chat_session(...) -> ChatSession`
- `get_chat_session(...) -> Optional[ChatSession]`
- `list_chat_sessions(...) -> List[ChatSession]`
- `update_chat_session(...) -> None`
- `append_chat_message(...) -> None`
- `delete_chat_session(...) -> None`
- `get_user_profile(...) -> Optional[UserProfile]`
- `upsert_user_profile(...) -> None`
- `get_context(...) -> Optional[ContextState]`
- `get_or_create_context(...) -> ContextState`
- `save_context(...) -> None`
- `list_context_names(...) -> List[str]`
- `list_tasklists(...) -> List[str]`
- `get_tasklist(...) -> Optional[TaskList]`
- `save_tasklist(...) -> None`
- `delete_tasklist(...) -> None`
- `list_documents(...) -> List[DocumentRef]`
- `get_document(...) -> Optional[DocumentRef]`
- `upsert_document(...) -> None`
- `upsert_embedding(...) -> None`
- `query_embeddings(...) -> List[Tuple[EmbeddingRecord, float]]`
- `delete_embeddings(...) -> int`
---
tags:
  - path
  - str
  - property
  - storage_path
  - module
  - storagepath
  - base
  - doc
  - source
  - resolver
  - src/storage_paths
---

# `src/storage_paths`

## Source files
- `src/storage_paths/storage_paths.py`

## Summary (short)
- Central resolver for all on-disk storage paths; prevents path traversal and defines per-domain index locations.

## Key classes
### `StoragePaths` (`src/storage_paths/storage_paths.py`)
Centralised, authoritative resolver for all user-data paths.

Key responsibilities:
- Resolves a **storage base** from `storage_root_path` + `storage_namespace`.
- Guards against namespace escaping the root (`ValueError` if misconfigured).
- Exposes domain base directories: `contexts`, `chats`, `documents`, `tasklists`, `users`, `agents`.
- Safely resolves user-supplied relative paths under the storage base.
- Builds domain-local index paths.

## Dependencies
- **stdlib:** `pathlib.Path`

## Methods (service/base class)
### `StoragePaths`
- `__init__(storage_root_path: str, storage_namespace: str)`
- `resolve_relative(self, relative_path: str) -> Path`
- `index_for(self, domain: str, account: str, filename: str = "index.json") -> Path`
- `domain_index(self, domain: str, *subpaths: str) -> Path`
---
tags:
  - json
  - module
  - serialization
  - to_dict
  - from_dict
  - to_json
  - from_json
  - doc
  - source
  - tasklistservice
  - boundary
  - creation
  - src/tasklists
---

# `src/tasklists`

## Source files
- `src/tasklists/__init__.py`
- `src/tasklists/service.py`
- `src/tasklists/task_list.py`
- `src/tasklists/task.py`
- `src/tasklists/task_states.py`

## Summary (short)
- Tasklist domain model + service boundary for creating, validating, saving, and running multi-step work.

## Key classes
- **`TaskListService`** (`service.py`)
- **`TaskList`** (`task_list.py`)
- **`Task`** (`task.py`)
- **State constants** (`task_states.py`)

## Dependencies
- **stdlib:** `json`, `uuid`, `dataclasses`, `typing`
- **third-party:** `pydantic`
- **internal:** `src.tasklists.task_states`
---
tags:
  - util
  - json
  - module
  - utils
  - account_name
  - query
  - list[documentref
  - yaml
  - base
  - doc
  - source
  - get_document_context(storage
  - src/utils
---

# `src/utils` mini doc

## Summary (short)
- Small helpers for document snippet loading, Obsidian import, and one-off migrations.

## Source files
- `src/utils/document_context.py`
- `src/utils/text_snippet_loader.py`
- `src/utils/obsidian_importer.py`
- `src/utils/migrate_legacy_completions.py`

## Key functions / classes
### `get_document_context(...)` (in `document_context.py`)
Thin helper over the storage layer to fetch document snippets for prompt context.

### `load_text_snippet(...)` (in `text_snippet_loader.py`)
Reads a text file and returns a bounded snippet.

### `index_obsidian_vault(...)` (in `obsidian_importer.py`)
Walks an Obsidian vault and upserts `DocumentRef` entries into storage.

### `migrate(...)` (in `migrate_legacy_completions.py`)
One-off migration script for legacy completions.
---

tags:
  - flask
  - api
  - routes
  - swagger
  - cors
  - logging
  - request_id
  - tasklists
  - chats
  - documents
  - app
---

# `app.py`

## Purpose
Flask entrypoint for the Lucy HTTP API. Wires DI/container services, config, logging, and defines the REST endpoints.

## Summary (short)
- Initializes Flask + CORS, loads `config.json`, and configures rotating file logging with a per-request `request_id`.
- Serves OpenAPI (`/swagger.json`) and Swagger UI.
- Exposes core API routes:
  - `/ask` (main chat endpoint; delegates to `AskRequestHandler`)
  - chat CRUD (`/chats`, `/chats/<id>`, `/chats/<id>/messages`)
  - context names (`/context/names`)
  - tasklists CRUD (`/tasklists`, `/tasklists/<name>`)
  - agents list (`/agents`)
  - prompt builder debug endpoint (`/prompt_builder`)
  - document search (`/documents/search`)
- Handles friendlyName-based session resume/creation when `conversationId` is missing.
- Runs with TLS when executed directly (`__main__`).

## Key components
- Logging: `configure_logging()` uses `RotatingFileHandler` and `RequestIdFilter` (injects `request_id_var`).
- DI: uses `container.get(...)` to resolve `Storage`, `AgentManager`, `AskRequestHandler`, and `PromptBuilder`.
- Request hooks: `before_request` sets request id + start timestamp; `after_request`/`teardown_request` clear it.

## Dependencies
- **third-party:** `flask`, `flask_cors`, `flask_swagger_ui`
- **stdlib:** `logging`, `ssl`, `uuid`, `time`, `os`
- **internal:** `src.container_config.container`, `src.request_context.request_id_var`, `src.storage`, `src.agent`, `src.message_endpoints.ask_request_handler.AskRequestHandler`, `src.prompt_builders.prompt_builder.PromptBuilder`
