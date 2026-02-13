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
