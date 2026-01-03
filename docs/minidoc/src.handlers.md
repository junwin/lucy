---
tags:
  - Handler
  - HandlerV2
  - HandlerRegistry
  - FileLoadHandler2
  - FileSaveHandler
  - PlanTasksHandler
  - ScrapeWebPageHandler2
  - CommandExecutionHandler2
  - WebSearchHandler2
  - src.handlers
  - handlers
  - src.handlers
---

# src.handlers

Short description: Core tool handler layer for Lucy. Defines the handler interfaces and concrete tool implementations used by FunctionCallingProcessor and other components.

## Python files and key classes

- `src/handlers/__init__.py`
  - (no classes)

- `src/handlers/handler.py`
  - `Handler` – legacy abstract handler interface with `handle` and `get_function_calling_definition`.

- `src/handlers/handler_v2.py`
  - `HandlerV2` – abstract base class for the new-style tool handlers with `name`, `tool_def`, `result_schema`, and `execute`.

- `src/handlers/handler_registry.py`
  - `HandlerRegistry` – registry mapping handler names to `HandlerV2` subclasses, used to create handlers and expose tool definitions and result schemas.

- `src/handlers/registry_bootstrap.py`
  - (no new classes; builds and populates a `HandlerRegistry` with concrete handlers.)

- `src/handlers/file_load_handler2.py`
  - `FileLoadHandler2` – safe file-loading handler (`file_load` tool) that enforces base-path and path-safety rules.

- `src/handlers/file_save_handler.py`
  - `FileSaveHandler2` – safe file-writing handler (`file_save` tool) mirroring the safety model of `FileLoadHandler2`.

- `src/handlers/plan_tasks_handler.py`
  - `PlanTasksHandler` – planning-only handler (`plan_tasks` tool) that generates simple sequential task lists for later execution.

- `src/handlers/scrape_web_page_handler2.py`
  - `ScrapeWebPageHandler2` – handler (`scrape_web_page` tool) that runs an external script to scrape webpage text.

- `src/handlers/command_execution_handler2.py`
  - `CommandExecutionHandler2` – handler (`execute_command` tool) that runs OS commands in a constrained working directory.

- `src/handlers/web_search_handler2.py`
  - `WebSearchHandler2` – handler (`web_search_handler` tool) that calls the Brave Search API and normalizes results.

- `src/handlers/handler_utils.py`
  - (no classes; helper functions such as `get_base_path`, `execute_script`, etc.)
