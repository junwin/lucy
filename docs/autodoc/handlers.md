---
tags:
  - result_schema
  - classmethod
  - tool_def
  - handlerregistry
  - tool_names
  - all_result_schemas
  - module
  - handler
  - handlerv2
  - base
  - src/handlers
---

# Module: `src/handlers`

## Key Classes

| Class | File | Description |
|-------|------|-------------|
| `HandlerV2` | `handler_v2.py` | Abstract base class — contract for all tool handlers |
| `HandlerRegistry` | `handler_registry.py` | Registry: register, create, and discover handlers by name |
| `FileLoadHandler2` | `file_load_handler2.py` | Safely read text files from named locations |
| `FileSaveHandler2` | `file_save_handler.py` | Safely write text files to named locations |
| `CommandExecutionHandler2` | `command_execution_handler2.py` | Run commands in a sandboxed working directory |
| `ScrapeWebPageHandler2` | `scrape_web_page_handler2.py` | Scrape a web page via a utility script |
| `WebSearchHandler2` | `web_search_handler2.py` | Brave Search API wrapper (optional — needs credentials) |
| `DelegateTasksHandler` | `delegate_tasks_handler.py` | Produce a sequential task list from a high-level goal |
| `GetKeywordsHandler` | `get_keywords_handler.py` | Keyword extraction via spaCy/NLTK/sklearn (optional) |
| `TasklistsManageHandler` | `tasklists_manage_handler.py` | CRUD for persisted tasklists |
| `TasklistsRunHandler` | `tasklists_run_handler.py` | Execute a persisted tasklist sequentially |

## Source Files

```
__init__.py
handler.py                  (legacy interface)
handler_v2.py               (HandlerV2 ABC)
handler_registry.py         (HandlerRegistry)
registry_bootstrap.py       (build_registry())
handler_utils.py            (get_base_path, execute_script, etc.)
schema_handler_v2.py        (shared JSON schema helpers)
file_load_handler2.py
file_save_handler.py
command_execution_handler2.py
scrape_web_page_handler2.py
web_search_handler2.py
delegate_tasks_handler.py
get_keywords_handler.py
tasklists_manage_handler.py
tasklists_run_handler.py
```

## Dependencies

**Standard library:** `abc`, `enum`, `json`, `logging`, `os`, `re`, `shlex`, `subprocess`

**Third-party:** `pydantic`, `requests`

**Internal (`src.*`):**
- `src.config_manager` — `ConfigManager`
- `src.keywords.keywords` — `Keywords`
- `src.message_processors.automation_processor` — `AutomationProcessor`
- `src.storage.json_file_storage` — `JsonFileStorage`
- `src.storage_paths.storage_paths` — `StoragePaths`
- `src.tasklists.task_list` — `TaskList`
- `src.tasklists.task_states` — `TASK_LIST_STATE_CREATED`, `TASK_STATE_PENDING`

## HandlerV2 Interface (Base Class)

Defined in `handler_v2.py`. All concrete handlers inherit from this ABC.

| Method | Type | Description |
|--------|------|-------------|
| `name()` | `@classmethod` | Returns the tool name string |
| `tool_def()` | `@classmethod` | Returns OpenAI-style tool definition dict |
| `result_schema()` | `@classmethod` | Optional — returns JSON schema for the result dict |
| `execute(args, *, account_name, **context)` | abstract | Executes the tool; returns a dict |

## HandlerRegistry Methods

| Method | Description |
|--------|-------------|
| `register(handler_cls)` | Register a `HandlerV2` subclass |
| `create(name, *, config)` | Instantiate a handler by name |
| `tools()` | Return list of all tool definitions |
| `tool_names()` | Return sorted list of registered handler names |
| `result_schema(name)` | Get result schema for a named handler |
| `all_result_schemas()` | Return dict of all cached result schemas |
