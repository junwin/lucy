---
tags:
  - src_handlers
  - lucyproject
  - HandlerV2
  - SchemaHandlerV2
  - HandlerRegistry
  - tool_def
  - execute_raw
  - registry_bootstrap
  - SandboxExecuteHandler
  - sandbox_execute
---

# Module: `src.handlers`

## Summary

The `src.handlers` package provides the **tool execution layer** for Lucy's function-calling system. Every tool the LLM can invoke (file load/save, command execution, web search, tasklist management, batched tool chaining, etc.) is implemented as a handler class in this package. The package defines the abstract handler interfaces, a registry for discovery, and concrete implementations for each tool.

## Key Classes

| Class | Base | Purpose |
|---|---|---|
| `HandlerV2` | `ABC` | Primary handler interface — defines `name()`, `tool_def()`, `result_schema()`, `execute()`. |
| `SchemaHandlerV2` | `ABC`, `Generic[ArgsT, ResultT]` | Typed handler base with Pydantic models for args/result validation and a `execute_raw()` JSON-string interface. |
| `HandlerRegistry` | — | Registry that maps handler names to handler classes; provides `tools()`, `create()`, `result_schema()`. |
| `Handler` | — | Legacy abstract handler (v1). Minimal — `handle()` and `get_function_calling_definition()`. |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Package exports — re-exports all concrete handlers for convenient imports. |
| `handler.py` | Legacy `Handler` base class (v1, minimal). |
| `handler_v2.py` | `HandlerV2` abstract base class — the current handler interface. |
| `schema_handler_v2.py` | `SchemaHandlerV2` — typed handler base with Pydantic validation and `execute_raw()`. |
| `handler_registry.py` | `HandlerRegistry` — name-based handler registration and lookup. |
| `handler_utils.py` | Utility functions: `get_base_path()` (sandbox path resolution), `execute_script()` (subprocess runner). |
| `registry_bootstrap.py` | `build_registry()` — factory that populates a `HandlerRegistry` with all available handlers. |
| `file_load_handler2.py` | `FileLoadHandler2` — load text files from storage or external roots. |
| `file_save_handler.py` | `FileSaveHandler2` — save text files to storage or external roots. |
| `command_execution_handler2.py` | `CommandExecutionHandler2` — run commands in sandboxed directories. |
| `scrape_web_page_handler2.py` | `ScrapeWebPageHandler2` — scrape text from a webpage URL. |
| `web_search_handler2.py` | `WebSearchHandler2` — search the web via Brave Search API. |
| `delegate_tasks_handler.py` | `DelegateTasksHandler` — plan a sequential task list for a goal. |
| `sandbox_execute_handler.py` | `SandboxExecuteHandler` — chain multiple tool calls in one batch with `$step_N.field` variable substitution. |
| `get_keywords_handler.py` | `GetKeywordsHandler` — extract keywords from text (optional NLP deps). |
| `tasklists_manage_handler.py` | `TasklistsManageHandler` — CRUD operations on persisted tasklists. |
| `tasklists_run_handler.py` | `TasklistsRunHandler` — execute a persisted tasklist via `AutomationProcessor`. |

## Dependencies

- **Standard library**: `abc`, `json`, `logging`, `os`, `re`, `shlex`, `subprocess`, `enum`, `typing`
- **Third-party**: `requests` (web search), `pydantic` (schema handler)
- **Internal**: `src.config_manager.ConfigManager`, `src.storage.json_file_storage.JsonFileStorage`, `src.storage_paths.storage_paths.StoragePaths`, `src.tasklists.*`, `src.keywords.keywords.Keywords`, `src.message_processors.automation_processor.AutomationProcessor`
- **Optional**: `spaCy`, `nltk`, `scikit-learn` (for `GetKeywordsHandler`)

## Methods — `HandlerV2` (service/base class)

| Method | Type | Signature | Description |
|---|---|---|---|
| `name` | `@classmethod @abstractmethod` | `() -> str` | Return the tool name (e.g. `"file_load"`). |
| `tool_def` | `@classmethod @abstractmethod` | `() -> Dict[str, Any]` | Return the OpenAI tool definition dict. |
| `result_schema` | `@classmethod` | `() -> Optional[Dict[str, Any]]` | Return optional JSON schema for the result dict. |
| `execute` | `@abstractmethod` | `(args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Execute the tool with parsed arguments. |

## Methods — `SchemaHandlerV2` (typed base)

| Method | Type | Signature | Description |
|---|---|---|---|
| `name` | `@classmethod @abstractmethod` | `() -> str` | Return the tool name. |
| `tool_def` | `@classmethod @abstractmethod` | `() -> Dict[str, Any]` | Return the OpenAI tool definition dict. |
| `result_schema` | `@classmethod` | `() -> Optional[Dict[str, Any]]` | Return JSON schema derived from `ResultModel`. |
| `execute_raw` | (instance) | `(arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Execute with raw JSON string; validates args via `ArgsModel`, calls `execute()`, validates result via `ResultModel`. |
| `execute` | `@abstractmethod` | `(args: ArgsT, *, account_name: str = "auto", call_id: str = "") -> ResultT | Dict[str, Any]` | Execute the tool with typed Pydantic args. |
| `_execute_typed` | (instance) | `(args: Dict[str, Any], *, account_name: str, call_id: str) -> str` | Internal: validate args dict, call `execute()`, validate result, serialize. |
| `_dump_result` | (instance) | `(result_obj: BaseModel, *, call_id: str) -> str` | Serialize a Pydantic model to JSON string. |

## Methods — `HandlerRegistry`

| Method | Signature | Description |
|---|---|---|
| `register` | `(handler_cls: Type[HandlerV2]) -> None` | Register a handler class by name. |
| `create` | `(name: str, *, config: Any) -> HandlerV2` | Instantiate a handler by name. |
| `tools` | `() -> List[Dict[str, Any]]` | Return tool definitions for all registered handlers. |
| `tool_names` | `() -> List[str]` | Return sorted list of registered handler names. |
| `result_schema` | `(name: str) -> Optional[Dict[str, Any]]` | Return result schema for a named handler. |
| `all_result_schemas` | `() -> Dict[str, Dict[str, Any]]` | Return all cached result schemas. |
