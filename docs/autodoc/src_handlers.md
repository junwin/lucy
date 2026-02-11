---
tags:
  - handler
  - handlerv2
  - handlerregistry
  - getkeywordshandler
  - str
  - websearchhandler2
  - root
  - interface
  - implementation
  - command
  - src/handlers
---

# `src/handlers`

## Purpose
- Defines the tool/handler layer used by the Function Calling Processor (FCP).
- Provides a common handler interface (`HandlerV2`) and a registry (`HandlerRegistry`) to register and expose tools.
- Includes concrete `HandlerV2` implementations for file IO, command execution, web scraping/search, keyword extraction, task planning, and tasklist management.

## Source files
- `src/handlers/__init__.py` (package exports; lazy import for optional `GetKeywordsHandler`)
- `src/handlers/handler.py` (legacy abstract `Handler`)
- `src/handlers/handler_v2.py` (`HandlerV2` ABC)
- `src/handlers/handler_registry.py` (`HandlerRegistry`)
- `src/handlers/registry_bootstrap.py` (`build_registry()` registers available handlers)
- `src/handlers/handler_utils.py` (shared helper utilities)
- `src/handlers/schema_handler_v2.py` (schema-related handler)
- `src/handlers/file_load_handler2.py` (`FileLoadHandler2`)
- `src/handlers/file_save_handler.py` (`FileSaveHandler2`)
- `src/handlers/command_execution_handler2.py` (`CommandExecutionHandler2`)
- `src/handlers/scrape_web_page_handler2.py` (`ScrapeWebPageHandler2`)
- `src/handlers/web_search_handler2.py` (`WebSearchHandler2`)
- `src/handlers/get_keywords_handler.py` (`GetKeywordsHandler`; optional heavy NLP deps)
- `src/handlers/plan_tasks_handler.py` (`PlanTasksHandler`)
- `src/handlers/tasklists_manage_handler.py` (`TasklistsManageHandler`)

## Key classes
- `HandlerV2` (`src/handlers/handler_v2.py`)
  - Contract for tool handlers: `name()`, `tool_def()`, `result_schema()` (optional), `execute(args, account_name)`.
- `HandlerRegistry` (`src/handlers/handler_registry.py`)
  - Stores handler classes by tool name, caches result schemas, exposes tool definitions, and instantiates handlers.
- Concrete `HandlerV2` implementations
  - `FileLoadHandler2`: safe relative-path file loading from storage/external roots.
  - `FileSaveHandler2`: safe relative-path file saving to storage/external roots.
  - `CommandExecutionHandler2`: safe command execution in sandbox/external roots.
  - `ScrapeWebPageHandler2`: fetches and extracts text from a URL.
  - `WebSearchHandler2`: web search tool (optional/config dependent).
  - `GetKeywordsHandler`: keyword extraction via `src.keywords.keywords.Keywords`.
  - `PlanTasksHandler`: creates a sequential task plan for a coding/refactoring goal.
  - `TasklistsManageHandler`: list/get/put/delete persisted tasklists via `JsonFileStorage`.

## Methods in the main service/base class
### `HandlerV2` (base interface)
- `@classmethod name() -> str`
- `@classmethod tool_def() -> dict`
- `@classmethod result_schema() -> dict | None`
- `execute(args: dict, *, account_name: str = "auto") -> dict`

### `HandlerRegistry` (main service)
- `__init__()`
- `register(handler_cls: Type[HandlerV2]) -> None`
- `create(name: str, *, config: Any) -> HandlerV2`
- `tools() -> list[dict]`
- `tool_names() -> list[str]`
- `result_schema(name: str) -> dict | None`
- `all_result_schemas() -> dict[str, dict]`

### `build_registry()` (`src/handlers/registry_bootstrap.py`)
- `build_registry() -> HandlerRegistry`
  - Registers core handlers and conditionally registers optional handlers (`WebSearchHandler2`, `GetKeywordsHandler`).
