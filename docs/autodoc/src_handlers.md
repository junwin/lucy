---
tags:
  - handler
  - interface
  - handlerv2
  - abc
  - str
  - dict[str
  - base
  - schemahandlerv2
  - handlerregistry
  - text
  - tool_def
  - result_schema
  - registry
  - legacy
  - fileloadhandler2
  - src/handlers
---

# Module: `src/handlers` — Tool Handler Layer

## Key Classes

| Class | Type | Description |
|-------|------|-------------|
| `HandlerV2` | ABC | Abstract base interface: `name()`, `tool_def()`, `result_schema()`, `execute()` |
| `SchemaHandlerV2` | ABC, Generic | Typed handler base with Pydantic `ArgsModel`/`ResultModel` validation |
| `HandlerRegistry` | Concrete | Maps handler names → handler classes, caches result schemas |
| `Handler` | ABC (legacy) | Old interface: `handle()`, `get_function_calling_definition()` |
| `FileLoadHandler2` | HandlerV2 | Safely reads text files from named locations (storage or external) |
| `FileSaveHandler2` | HandlerV2 | Safely writes text files to named locations with overwrite control |
| `CommandExecutionHandler2` | HandlerV2 | Runs commands in sandboxed working directories (`shell=False`) |
| `ScrapeWebPageHandler2` | HandlerV2 | Scrapes web pages via a utility script |
| `WebSearchHandler2` | HandlerV2 | Calls Brave Search API, returns normalized results |
| `GetKeywordsHandler` | HandlerV2 | Extracts keywords from text (spaCy/NLTK/sklearn) |
| `DelegateTasksHandler` | HandlerV2 | Plans sequential task lists for coding/refactoring goals |
| `TasklistsManageHandler` | HandlerV2 | CRUD operations for persisted tasklists |
| `TasklistsRunHandler` | HandlerV2 | Executes persisted tasklists via `AutomationProcessor` |

## Source Files (17 files)

- `__init__.py` — Package exports
- `handler.py` — Legacy `Handler` interface
- `handler_v2.py` — `HandlerV2` ABC interface
- `handler_registry.py` — `HandlerRegistry` class
- `handler_utils.py` — Utilities (`get_base_path`, `execute_script`)
- `registry_bootstrap.py` — `build_registry()` populates registry
- `schema_handler_v2.py` — `SchemaHandlerV2` typed base
- `file_load_handler2.py` — `FileLoadHandler2`
- `file_save_handler.py` — `FileSaveHandler2`
- `command_execution_handler2.py` — `CommandExecutionHandler2`
- `scrape_web_page_handler2.py` — `ScrapeWebPageHandler2`
- `web_search_handler2.py` — `WebSearchHandler2`
- `get_keywords_handler.py` — `GetKeywordsHandler`
- `delegate_tasks_handler.py` — `DelegateTasksHandler`
- `tasklists_manage_handler.py` — `TasklistsManageHandler`
- `tasklists_run_handler.py` — `TasklistsRunHandler`

## Dependencies

- **Standard library:** `os`, `json`, `logging`, `abc`, `enum`, `subprocess`, `shlex`, `re`, `pathlib`
- **Third-party:** `requests` (web_search), `pydantic` (schema_handler_v2), spaCy/nltk/sklearn (keywords, optional)
- **Internal:** `src.config_manager.ConfigManager`, `src.storage.json_file_storage.JsonFileStorage`, `src.storage_paths.storage_paths.StoragePaths`, `src.tasklists.task_list.TaskList`, `src.tasklists.task_states`, `src.keywords.keywords.Keywords`, `src.message_processors.automation_processor.AutomationProcessor`

## HandlerV2 Interface Methods

| Method | Type | Description |
|--------|------|-------------|
| `name()` | `@classmethod @abstractmethod -> str` | Handler name |
| `tool_def()` | `@classmethod @abstractmethod -> Dict[str, Any]` | OpenAI tool definition |
| `result_schema()` | `@classmethod -> Optional[Dict[str, Any]]` | JSON schema for returned dict (optional) |
| `execute(args, *, account_name="auto", **context)` | `@abstractmethod -> Dict[str, Any]` | Execute the tool |

## SchemaHandlerV2 Additional Methods

| Method | Description |
|--------|-------------|
| `execute_raw(arguments_raw, *, account_name, call_id) -> str` | Execute with raw JSON string arguments |
| `_execute_typed(args, *, account_name, call_id) -> str` | Validate args via Pydantic, call `execute()`, validate result |
| `_dump_result(result_obj, *, call_id) -> str` | Serialize result model to JSON string |

## HandlerRegistry Methods

| Method | Description |
|--------|-------------|
| `register(handler_cls) -> None` | Register a handler class |
| `create(name, *, config) -> HandlerV2` | Instantiate a handler by name |
| `tools() -> List[Dict[str, Any]]` | All tool definitions |
| `tool_names() -> List[str]` | All registered handler names |
| `result_schema(name) -> Optional[Dict[str, Any]]` | Schema for a specific handler |
| `all_result_schemas() -> Dict[str, Dict[str, Any]]` | All cached result schemas |
