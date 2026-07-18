---
tags:
  - src_handlers
  - lucyproject
  - HandlerV2
  - SchemaHandlerV2
  - HandlerRegistry
  - ErrorCode
  - ResultEnvelope
  - FileLoadHandler2
  - FileSaveHandler2
  - CommandExecutionHandler2
  - ScrapeWebPageHandler2
  - WebSearchHandler2
  - DelegateTasksHandler
  - Chat2Handler
  - CurateChatHandler
  - TasklistsManageHandler
  - TasklistsRunHandler
  - GetKeywordsHandler
  - SandboxExecuteHandler
  - build_registry
---

## 1. Summary

The `src/handlers` module is the **tool-implementation layer** of Lucy. It defines:

- Abstract handler interfaces (`Handler`, `HandlerV2`, `SchemaHandlerV2`) that prescribe how tools expose their OpenAI function-calling definitions, validate arguments, and execute.
- A **registry** (`HandlerRegistry`) that stores all available handlers by name, letting the rest of the system discover and instantiate them dynamically.
- A **bootstrap** function (`build_registry`) that wires up all concrete handler implementations.
- Twelve **concrete handlers** covering file I/O, command execution, web search/scrape, keyword extraction, task delegation, tasklist management/execution, chat session management, chat curation, and batched tool chaining.
- Shared **utility code** for path resolution (`get_base_path`) and script execution (`execute_script`).

It solves the problem of decoupling tool definitions from the LLM message-processing pipeline: processors like `FunctionCallingProcessor` ask the registry for tool definitions (to pass to the model) and for handler instances (to execute tool calls), without knowing about any specific handler.

## 2. Architecture & Design

### Three-tier handler interface hierarchy

| Tier | Class | Purpose |
|------|-------|---------|
| Legacy | `Handler` | Abstract stub with `handle()` and `get_function_calling_definition()`. No longer actively used. |
| Current | `HandlerV2` (ABC) | Requires `name()`, `tool_def()`, optional `result_schema()`, and `execute(args, ...)`. Accepts raw `Dict[str, Any]` args. |
| Typed | `SchemaHandlerV2` (ABC, Generic) | Extends the concept with Pydantic `ArgsModel` / `ResultModel`. Adds `execute_raw()` which accepts a JSON string, parses it, validates via Pydantic, calls `execute()`, validates the result, and re-serializes to JSON. Has no concrete handlers in the codebase yet — it is infrastructure for future handlers. |

### Registry pattern

`HandlerRegistry` is a simple in-memory map from handler name → handler class. It is **populated once at startup** by `build_registry()` in `registry_bootstrap.py`, then injected via the `injector` DI framework (`HandlerRegistryModule` in `container_config.py`). Handlers with optional heavy dependencies (e.g. `GetKeywordsHandler` which needs spaCy/nltk/sklearn) are imported lazily and silently skipped if dependencies are missing.

### Concrete handler design

Most concrete handlers follow this pattern:
1. Accept `ConfigManager` in `__init__`.
2. Provide `name()` (classmethod, returns the tool name string).
3. Provide `tool_def()` (classmethod, returns the OpenAI function definition dict with `strict=True`).
4. Provide `result_schema()` (classmethod, returns a JSON Schema for the result).
5. Implement `execute(args, *, account_name, **context)` → `Dict[str, Any]`.
6. Implement `execute_raw(arguments_raw, *, account_name, call_id)` → `str` (for compatibility with processors that call handlers via raw JSON).

### Shared concerns extracted to `handler_utils.py`

Path resolution (`get_base_path`) and script execution (`execute_script`) are shared by `FileLoadHandler2`, `FileSaveHandler2`, `CommandExecutionHandler2`, and `ScrapeWebPageHandler2`.

### Optional dependency handling

`GetKeywordsHandler` is guarded by a `try/except` at multiple levels — in `__init__.py` (package-level import), in `registry_bootstrap.py` (registration), and its own implementation defers model loading to the `Keywords` class. This ensures the entire module imports cleanly even without NLP libraries.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|-------|-------------|---------|
| `Handler` | `object` | Legacy abstract handler (stub). |
| `HandlerV2` | `ABC` | Current abstract handler interface. |
| `SchemaHandlerV2` | `ABC`, `Generic[ArgsT, ResultT]` | Typed handler with Pydantic validation. Currently unused by concrete handlers. |
| `HandlerRegistry` | `object` | Registry mapping handler names → classes; provides `tools()`, `tool_names()`, `create()`. |
| `ErrorCode` | `str, Enum` | Shared error code enum for tool results. |
| `ResultEnvelope` | `pydantic.BaseModel` | Base result envelope (`ok`, `tool`, `error`, `error_code`). |
| `FileLoadHandler2` | `HandlerV2` | Load a text file from storage or external root. |
| `FileSaveHandler2` | `HandlerV2` | Save a text file to storage or external root. |
| `CommandExecutionHandler2` | `HandlerV2` | Execute a command in a sandboxed directory. |
| `ScrapeWebPageHandler2` | `HandlerV2` | Scrape text from a webpage via `src/utils/scrape.py`. |
| `WebSearchHandler2` | `HandlerV2` | Search the web via Brave Search API. |
| `DelegateTasksHandler` | `HandlerV2` | Plan a sequential task list from a goal. |
| `Chat2Handler` | `HandlerV2` | CRUD and search for chat2 sessions. |
| `CurateChatHandler` | `HandlerV2` | Curate chat sessions (filter, summarize, archive). |
| `SandboxExecuteHandler` | `HandlerV2` | Chain multiple tool calls in one batch with `$step_N.field` variable substitution. |
| `TasklistsManageHandler` | `HandlerV2` | CRUD for persisted tasklists (list/get/put/patch/delete/reset). |
| `TasklistsRunHandler` | `HandlerV2` | Execute a persisted tasklist via `AutomationProcessor`. |
| `GetKeywordsHandler` | `HandlerV2` | Extract keywords from text using NLP libraries. |

## 4. Source Files

| File | Responsibility | Notable Exports |
|------|----------------|-----------------|
| `__init__.py` | Package exports; optional import of `GetKeywordsHandler`. | `FileLoadHandler2`, `FileSaveHandler2`, `CommandExecutionHandler2`, `ScrapeWebPageHandler2`, `WebSearchHandler2`, `DelegateTasksHandler`, `Chat2Handler`, `GetKeywordsHandler` (optional) |
| `handler.py` | Legacy abstract `Handler` class. | `Handler` |
| `handler_v2.py` | Current abstract `HandlerV2` ABC. | `HandlerV2` |
| `schema_handler_v2.py` | Typed handler base with Pydantic validation + shared enums/models. | `SchemaHandlerV2`, `ErrorCode`, `ResultEnvelope` |
| `handler_registry.py` | Registry that stores handler classes by name and exposes `tools()` / `create()`. | `HandlerRegistry` |
| `registry_bootstrap.py` | Builds and populates a `HandlerRegistry` with all concrete handlers. | `build_registry()` |
| `handler_utils.py` | Shared path resolution and script execution utilities. | `get_base_path()`, `execute_script()` |
| `file_load_handler2.py` | `file_load` tool — loads a text file from storage or external root. | `FileLoadHandler2` |
| `file_save_handler.py` | `file_save` tool — saves a text file to storage or external root. | `FileSaveHandler2` |
| `command_execution_handler2.py` | `execute_command` tool — runs a command in a sandboxed directory. | `CommandExecutionHandler2` |
| `scrape_web_page_handler2.py` | `scrape_web_page` tool — scrapes text from a URL. | `ScrapeWebPageHandler2` |
| `web_search_handler2.py` | `web_search_handler` tool — searches the web via Brave Search. | `WebSearchHandler2` |
| `delegate_tasks_handler.py` | `delegate_tasks` tool — plans a task list from a goal. | `DelegateTasksHandler` |
| `chat2_handler.py` | `chat2_handler` tool — manages chat2 sessions (CRUD, search, curate). | `Chat2Handler` |
| `curate_chat_handler.py` | `curate_chat` tool — curates sessions via `CurationEngine` (filter, summarize, archive). | `CurateChatHandler` |
| `sandbox_execute_handler.py` | `sandbox_execute` tool — chains multiple tool calls in one batch with variable substitution. | `SandboxExecuteHandler` |
| `tasklists_manage_handler.py` | `tasklists_manage` tool — CRUD + patch + reset for persisted tasklists. | `TasklistsManageHandler` |
| `tasklists_run_handler.py` | `tasklists_run` tool — executes a persisted tasklist via `AutomationProcessor`. | `TasklistsRunHandler` |
| `get_keywords_handler.py` | `get_keywords` tool — extracts keywords from text (requires NLP deps). | `GetKeywordsHandler` |

## 5. Dependencies

### Standard library
`os`, `json`, `shlex`, `subprocess`, `logging`, `re`, `abc` (`ABC`, `abstractmethod`), `enum` (`Enum`), `typing` (`Any`, `Dict`, `List`, `Optional`, `Tuple`, `Type`, `TypeVar`, `Generic`), `pathlib` (`Path`)

### Third-party packages
- **pydantic** — `BaseModel`, `ValidationError` (used in `schema_handler_v2.py`)
- **requests** — HTTP client for Brave Search API (used in `web_search_handler2.py`)
- **spaCy / nltk / scikit-learn** — Optional NLP dependencies for keyword extraction (used indirectly via `src.keywords.keywords.Keywords` in `get_keywords_handler.py`)

### Internal modules
- `src.config_manager` — `ConfigManager` (injected into every concrete handler)
- `src.chat2.facade` — `Chat2Store` (used by `Chat2Handler`, `CurateChatHandler`)
- `src.chat2.models` — `ChatEvent` (used by `Chat2Handler`)
- `src.chat2.adapters.jfs_adapter` — `JfsChat2Primitives` (constructed inside `Chat2Handler._build_store()`)
- `src.storage.json_file_storage` — `JsonFileStorage` (used by `Chat2Handler`, `CurateChatHandler`, `TasklistsManageHandler`)
- `src.storage_paths.storage_paths` — `StoragePaths` (used by `Chat2Handler`, `CurateChatHandler`, `TasklistsManageHandler`)
- `src.curation.core` — `CurationEngine` (used by `CurateChatHandler`)
- `src.curation.resolver` — `resolve_session` (imported but apparently unused directly in `CurateChatHandler`)
- `src.llm.interface` — `LLMApi` (used by `CurateChatHandler`)
- `src.llm.router_api` — `RouterApi` (used by `CurateChatHandler`)
- `src.tasklists.task` — `Task` (used by `TasklistsManageHandler`)
- `src.tasklists.task_list` — `TaskList` (used by `TasklistsManageHandler`)
- `src.tasklists.task_states` — `TASK_LIST_STATE_CREATED`, `TASK_STATE_PENDING` (used by `TasklistsManageHandler`)
- `src.message_processors.automation_processor` — `AutomationProcessor` (used by `TasklistsRunHandler`)
- `src.keywords.keywords` — `Keywords` (used by `GetKeywordsHandler`)
- `src.handlers.handler_utils` — `execute_script` (used by `ScrapeWebPageHandler2`)
- `src.handlers.handler_registry` — `HandlerRegistry` (used by `SandboxExecuteHandler`)

### Optional dependencies
- `GetKeywordsHandler` — guarded at import and registration time; requires spaCy, nltk, scikit-learn.
- `WebSearchHandler2` — guarded at registration time in `build_registry()`; requires Brave Search credentials.

## 6. Configuration / Settings

All handlers receive a `ConfigManager` instance. The following config keys are read:

| Key | Type | Default | What it controls |
|-----|------|---------|------------------|
| `storage_root_path` | `str` | — | Base directory for Lucy storage (used by `FileLoadHandler2`, `FileSaveHandler2`, `Chat2Handler`, `CurateChatHandler`) |
| `storage_namespace` | `str` | — | Subdirectory under storage root (e.g. `"data"`) |
| `external_roots` | `dict[str, str]` | `{}` | Map of named external root keys → filesystem paths (used by file and command handlers) |
| `code_sandbox_path` | `str` | — | Base directory for sandboxed command execution (used by `CommandExecutionHandler2` and `handler_utils.get_base_path`) |
| `credential_path` | `str` | — | Directory containing credential files (used by `WebSearchHandler2` to load `brave.json`) |
| `curation_llm_model` | `str` | `"gpt-4o-mini"` | LLM model used for chat curation summaries (used by `CurateChatHandler`) |

Environment variables read (by `handler_utils.get_base_path`):
- `LUCY_USER_ROOT` — overrides the account root resolution
- `HOME` — fallback for account root resolution

If none: many handlers rely on `ConfigManager` and will raise `ValueError` if required keys are missing.

## 7. Exceptions

None. No custom exception classes are defined in this module. Handlers raise built-in exceptions (`ValueError`, `FileNotFoundError`, `FileExistsError`, `KeyError`) or return structured error dicts with `"ok": False`.

## 8. Module-Level Constants

| Constant | Defined in | Value | Purpose |
|----------|-----------|-------|---------|
| `MAX_OUTPUT_CHARS` | `command_execution_handler2.py` | `10_000` | Max characters of stdout/stderr to return; output beyond this is truncated with a marker. |
| `INTERACTIVE_BARE` | `command_execution_handler2.py` | `{"python", "python3", "bash", "sh", "zsh"}` | Set of interpreter names that are rejected when called with no arguments (to prevent hanging on stdin). |
| `BRAVE_ENDPOINT` | `web_search_handler2.py` | `"https://api.search.brave.com/res/v1/web/search"` | Brave Search API endpoint URL. |
| `_VAR_RE` | `sandbox_execute_handler.py` | `re.compile(r"\$step_(\d+)\.(\S+)")` | Regex for matching `$step_N.field` variable references in step args. |

Additionally, each concrete handler defines a `NAME` class attribute (e.g. `"file_load"`, `"file_save"`) used as the tool name.

## 9. Methods (by class)

### Handler (legacy)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `handle` | instance | `handle(self, request, account_name: str = "auto")` | Stub — does nothing. Legacy entry point for old-style tool calls. |
| `get_function_calling_definition` | instance | `get_function_calling_definition(self) -> str` | Stub — returns nothing. Legacy. |

### HandlerV2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `name` | classmethod (abstract) | `name(cls) -> str` | Returns the unique tool name (e.g. `"file_load"`). Used as the registry key. |
| `tool_def` | classmethod (abstract) | `tool_def(cls) -> Dict[str, Any]` | Returns the OpenAI function-calling definition dict (with `type`, `name`, `description`, `parameters`, `strict`). |
| `result_schema` | classmethod | `result_schema(cls) -> Optional[Dict[str, Any]]` | Returns an optional JSON Schema for the result dict. Defaults to `None`. |
| `execute` | instance (abstract) | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Executes the tool. Receives raw dict args and returns a structured result dict (must include `ok`). |

### SchemaHandlerV2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `name` | classmethod (abstract) | `name(cls) -> str` | Tool name. |
| `tool_def` | classmethod (abstract) | `tool_def(cls) -> Dict[str, Any]` | OpenAI function definition. |
| `result_schema` | classmethod | `result_schema(cls) -> Optional[Dict[str, Any]]` | Default: calls `ResultModel.model_json_schema()`. Falls back to `None` on error. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses `arguments_raw` as JSON, validates via `ArgsModel`, delegates to `execute()`, validates result via `ResultModel`, returns JSON string. Handles all error cases (invalid JSON, validation failure, execution exception, invalid result shape, serialization failure) and returns structured error JSON with appropriate `ErrorCode`. |
| `execute` | instance (abstract) | `execute(self, args: ArgsT, *, account_name: str = "auto", call_id: str = "") -> ResultT \| Dict[str, Any]` | The typed execution method. Subclasses receive a validated Pydantic `ArgsT` instance and return a `ResultT` or dict. |
| `_execute_typed` | instance | `_execute_typed(self, args: Dict[str, Any], *, account_name: str, call_id: str) -> str` | Validates raw args dict → `ArgsT`, calls `execute()`, validates result → `ResultT`, dumps to JSON. Internal pipeline step. |
| `_dump_result` | instance | `_dump_result(self, result_obj: BaseModel, *, call_id: str) -> str` | Dumps a `ResultEnvelope` or `ResultT` to JSON. Falls back to an error envelope on serialization failure. |

### HandlerRegistry

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `register` | instance | `register(self, handler_cls: Type[HandlerV2]) -> None` | Registers a handler class by its `name()`. Raises `ValueError` on empty name or duplicate. Caches `result_schema()` if available. |
| `create` | instance | `create(self, name: str, *, config: Any) -> HandlerV2` | Instantiates a handler by name, passing `config` to its constructor. Raises `KeyError` if unknown. |
| `tools` | instance | `tools(self) -> List[Dict[str, Any]]` | Returns the `tool_def()` for every registered handler (used to build the OpenAI tools list). |
| `tool_names` | instance | `tool_names(self) -> List[str]` | Returns sorted list of registered handler names. |
| `result_schema` | instance | `result_schema(self, name: str) -> Optional[Dict[str, Any]]` | Returns the cached or live `result_schema()` for a named handler. |
| `all_result_schemas` | instance | `all_result_schemas(self) -> Dict[str, Dict[str, Any]]` | Returns a copy of all cached result schemas. |

### FileLoadHandler2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Resolves location (`storage`/`external`), validates relative path, resolves base directory, reads file safely, returns dict with `result` (file content), `resolved_path`, `file_name`, `content_type`, etc. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses JSON args, calls `execute()`, returns JSON string. |
| `_validate_and_normalize_relative_path` | instance | `_validate_and_normalize_relative_path(self, path_in: str) -> Tuple[str, str]` | Rejects drive letters, absolute paths, empty/`.`/`..` paths, and `..` segments. Returns `(normalized, error_or_empty)`. |
| `_read_file_safe` | instance | `_read_file_safe(self, base_dir: str, rel_path: str) -> Tuple[str, str]` | Resolves `base_dir + rel_path`, checks containment via `realpath`, reads file as UTF-8. Returns `(content, full_real_path)`. |
| `_storage_base_dir` | instance | `_storage_base_dir(self) -> str` | Returns `<storage_root_path>/<storage_namespace>`. |
| `_external_root_dir` | instance | `_external_root_dir(self, external_root: str) -> str` | Looks up `external_roots[external_root]`. |
| `_has_drive_letter` | static | `_has_drive_letter(path: str) -> bool` | Returns `True` if path starts with a Windows drive letter (`C:`). |

### FileSaveHandler2

Same public interface as `FileLoadHandler2` plus:
- `execute_raw` also maps legacy `relative_path` → `path` and defaults missing `location`/`external_root`/`overwrite`.
- `_write_file_safe` creates parent directories, checks `overwrite`, writes content.

### CommandExecutionHandler2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Validates location/command/working_directory, rejects bare interactive interpreters and shell-only syntax, resolves and containment-checks the working directory, runs the command, truncates output, checks exit code against `success_exit_codes`. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses JSON, defaults missing fields, calls `execute()`. |
| `_is_bare_interactive` | instance | `_is_bare_interactive(self, command: str) -> bool` | Returns `True` if the command is `python`/`bash`/etc. with no arguments, or `bash` without `-c`/`-lc`. |
| `_contains_shell_syntax` | instance | `_contains_shell_syntax(self, command: str) -> bool` | Regex-detects shell metacharacters (pipes, redirects, `&&`, `||`, `$()`, backticks). Skips detection if command is already wrapped in `bash -c`/`bash -lc`. |
| `_truncate` | instance | `_truncate(self, text: str, limit: int = 10000) -> str` | If text exceeds `limit`, keeps first and last halves with a truncation marker. |
| `_execute_script` | instance | `_execute_script(self, command: str, cwd: str, timeout: int = 30) -> tuple[int, str, str]` | Splits command via `shlex`, runs with `subprocess.run(shell=False, cwd=cwd, timeout=timeout)`. Returns `(returncode, stdout, stderr)`. |

### ScrapeWebPageHandler2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Validates `page_url` is non-empty, delegates to `execute_script("python3 src/utils/scrape.py <url>", ".")`, returns scraped text. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses JSON, calls `execute()`. |

### WebSearchHandler2

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Validates `query` is non-empty, calls Brave Search API, returns list of `{url, name, description}` results. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses JSON, calls `execute()`. |
| `_brave_search` | instance | `_brave_search(self, *, query: str, count: int) -> List[Dict[str, Any]]` | Makes an HTTP GET to Brave Search with the subscription key header. |
| `_extract_results` | instance | `_extract_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]` | Pulls `web.results` from the API response and normalizes to `{url, name, description}`. |

### DelegateTasksHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Takes `goal`, optional `files` list, `instruction`, `worker_agent`. Returns a `tasklist` dict with one task per file (or one general task if no files). Default `worker_agent` is `"colin"`. |
| `execute_raw` | instance | `execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str` | Parses JSON, calls `execute()`. |

### Chat2Handler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Dispatches on `action` field to one of 7 private methods. |
| `_build_store` | static | `_build_store() -> Chat2Store` | Constructs a `JsonFileStorage` → `JfsChat2Primitives` → `Chat2Store` pipeline from config. |
| `_reset_chat` | instance | `_reset_chat(self, session_id: str) -> Dict` | Clears all events, keeps metadata. |
| `_search_sessions` | instance | `_search_sessions(self, query, account_name, agent_name, limit) -> Dict` | Lists sessions, filters those whose events contain the query string. |
| `_curate_session` | instance | `_curate_session(self, session_id, curation_rules_raw) -> Dict` | Applies `remove_kinds`, `keep_roles`, `deduplicate` rules to events, rewrites session. |
| `_get_session` | instance | `_get_session(self, session_id) -> Dict` | Returns session metadata + all events. |
| `_list_sessions` | instance | `_list_sessions(self, account_name, agent_name, limit) -> Dict` | Returns list of session metadata dicts. |
| `_delete_session` | instance | `_delete_session(self, session_id) -> Dict` | Deletes session and its events. |
| `_update_session` | instance | `_update_session(self, session_id, patch_fields_raw) -> Dict` | Parses JSON patch, maps friendly names (`friendly_name`, `friendlyName`, `tags`, `metadata`), calls `chat2_store.update_session()`. |
| `_meta_to_dict` | static | `_meta_to_dict(meta) -> Dict` | Converts `ChatSessionMeta` to a plain dict. |
| `_event_to_dict` | static | `_event_to_dict(event: ChatEvent) -> Dict` | Converts `ChatEvent` to a plain dict. |

### CurateChatHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Resolves session by `session_id` or `friendly_name`, calls `CurationEngine.curate()` with mode (`filter`/`summarize`/`archive`), preview/publish flags, template name, and curation rules. |
| `_build_store` | static | `_build_store()` | Constructs `Chat2Store` (same pattern as `Chat2Handler`). |
| `_build_engine` | instance | `_build_engine(self) -> CurationEngine` | Constructs `CurationEngine` with `Chat2Store`, `RouterApi`, LLM model from config, and paths for digests/archives under `lucy_data_files`. |

### SandboxExecuteHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", registry: Optional[HandlerRegistry] = None, **context) -> Dict[str, Any]` | Chains multiple tool calls sequentially. Each step specifies a `tool` name and `args` dict. Uses `$step_N.field` variable substitution (dot notation for nested fields, index into lists) to pipe results between steps. Supports `continue_on_error` (default false) to keep running after failures. Returns `{ok, tool, steps: [{step, tool, ok, result}], final}`. |
| `_resolve_vars` | instance | `_resolve_vars(self, value: Any, step_results: Dict[int, Dict[str, Any]]) -> Any` | Recursively replaces `$step_N.field` references in strings (and nested dicts/lists) with values from earlier step results. Dot notation traverses nested dicts; numeric parts index into lists. Returns the resolved value. |

### TasklistsManageHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Dispatches on `action`: `list` → lists tasklists; `get` → fetches one; `put` → validates and saves (with UUID-matching check for existing); `patch` → applies operations; `delete` → idempotent delete; `reset` → resets tasklist state to Created and all tasks to Pending. |
| `_handle_patch` | instance | `_handle_patch(self, account_name, tasklist_name, payload, validate_only) -> Dict` | Parses `operations` list, loads existing tasklist, applies each operation sequentially. Supports `add_task`, `update_task`, `remove_task`, `update_meta`, `set_general_instructions`, `set_name`, `set_description`. |
| `_apply_operation` | instance | `_apply_operation(self, tl, op_type, op, index) -> None` | Applies a single patch operation to a `TaskList` in place. |

### TasklistsRunHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Resolves `AutomationProcessor` from context or `processor_factory`, extracts `primary_agent`/`account`/`conversation_id`, calls `automation_processor.execute_tasklist()`. Mode must be `"single-step"` or `"multi-step"`. |

### GetKeywordsHandler

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `execute` | instance | `execute(self, args: Dict[str, Any], **context) -> Dict[str, Any]` | Validates `content` is non-empty, constructs `Keywords(language_code)`, calls `extract_keywords(content, top_n)`. |

### handler_utils (module-level functions)

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_base_path` | `get_base_path(config, account_name: str, relative_path: str = "") -> str` | Resolves a filesystem path under a per-account sandbox. Uses a 7-step hybrid strategy: env var `LUCY_USER_ROOT`, config `code_sandbox_path`, `$HOME`, `/home/<account>`, `/`. Rejects path traversal (`..`) and escape attempts. |
| `execute_script` | `execute_script(command: str, working_dir: str) -> str` | Executes a command via `subprocess.run(shell=False, cwd=working_dir)`. Returns stdout on success, formatted error on failure. 30-second timeout. Used by `ScrapeWebPageHandler2`. |

## 10. Usage Examples

### Constructing a handler and executing it

```python
from src.config_manager import ConfigManager
from src.handlers import FileLoadHandler2

config = ConfigManager("config.json")
handler = FileLoadHandler2(config)

result = handler.execute({
    "location": "external",
    "external_root": "repo_lucy",
    "path": "README.md",
})
# result["ok"] → True
# result["result"] → file content string
```

### Using the registry to discover and invoke tools

```python
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.registry_bootstrap import build_registry

registry = build_registry()

# Get all tool definitions for the OpenAI API
tools = registry.tools()
# tools → [{"type": "function", "name": "file_load", ...}, ...]

# Create and execute a handler by name
handler = registry.create("file_load", config=config)
result = handler.execute({"location": "storage", "external_root": "", "path": "index.json"})
```

### Chain tool calls with sandbox_execute

```python
handler = registry.create("sandbox_execute", config=config)
result = handler.execute({
    "steps": [
        {"tool": "scrape_web_page",    "args": {"page_url": "https://example.com"}},
        {"tool": "get_keywords",       "args": {"content": "$step_1.result", "top_n": 5, "language_code": "en"}},
        {"tool": "file_save",          "args": {"path": "keywords.txt", "file_content": "$step_2.keywords"}},
    ],
    "continue_on_error": False,
}, registry=registry)
# result["steps"] → [{step: 1, ok: True, ...}, {step: 2, ok: True, ...}, ...]
# result["final"] → result of the last step
```

### Patch a tasklist

```python
handler = registry.create("tasklists_manage", config=config)
result = handler.execute({
    "action": "patch",
    "tasklist_name": "my_tasks",
    "tasklist": {
        "operations": [
            {"op": "add_task", "task": {"id": "t1", "name": "Deploy", "instructions": "Run deploy script"}},
            {"op": "set_description", "description": "Updated workflow"},
        ]
    },
    "validate_only": False,
})
```

## 11. Edge Cases & Gotchas

1. **All handlers return `ok: False` + error string rather than raising exceptions.** The FCP and other callers inspect `ok`, not try/except. Exceptions are logged but caught and converted to error dicts.

2. **Strict tool schemas require all `properties` to be in `required`.** Every concrete handler's `tool_def()` declares `"strict": True` and includes every property key in the `required` array. This is an OpenAI API requirement. If the model omits a field, the API rejects the call.

3. **`CommandExecutionHandler2` double-checks shell safety.** It rejects bare interactive interpreters AND shell metacharacters. However, it allows `bash -lc "..."` as an escape hatch — once wrapped, pipe/redirect detection is bypassed.

4. **Path traversal is prevented at multiple levels.** `FileLoadHandler2`, `FileSaveHandler2`, and `CommandExecutionHandler2` all reject `..`, absolute paths, and drive letters. They also enforce containment via `os.path.realpath` comparison. `handler_utils.get_base_path` does the same for legacy callers.

5. **`WebSearchHandler2` reads credentials from disk at init time.** It opens `{credential_path}/brave.json` in `__init__`. This means it fails fast if the credential file is missing or malformed. Registration in `build_registry` is itself wrapped in try/except to handle this.

6. **`GetKeywordsHandler` is entirely optional.** It is guarded at the package `__init__.py`, at `build_registry()`, and its own code defers heavy NLP model loading. If spaCy/nltk/sklearn are not installed, the handler is simply unavailable — no other part of the system breaks.

7. **`Chat2Handler` and `CurateChatHandler` each construct their own `Chat2Store`.** They don't share an instance. Both call `_build_store()` which creates a fresh `JsonFileStorage` → `JfsChat2Primitives` → `Chat2Store` chain. This is safe for reads but means there's no in-memory cache shared between the two handlers.

8. **`TasklistsManageHandler.put` enforces UUID matching on replacement.** If you PUT over an existing tasklist, the incoming payload must include the same `id` as the stored tasklist, or the operation is rejected. This prevents accidental overwrites.

9. **`TasklistsRunHandler` requires runtime context.** It needs `automation_processor` (or `processor_factory`), `primary_agent`, and `account` passed via `**context` from the FCP. Without these, it returns an error. It cannot function standalone.

10. **`execute_raw` is the preferred entry point for processors.** While `execute()` accepts a dict, the FCP typically calls `execute_raw()` with a raw JSON string from the model. Handlers that implement both must keep them in sync.

11. **Output truncation.** `CommandExecutionHandler2` truncates stdout/stderr at 10,000 characters (keeping head + tail). If the full output is needed, a follow-up command like `tail` or `cat` with a specific path should be used.

12. **`SandboxExecuteHandler` requires a registry at runtime.** It needs a `HandlerRegistry` instance (passed via `registry` kwarg or injected via `**context`). Without it, the handler returns an error. The FCP's `_handle_tool_call` method provides this via `registry=registry` when calling `execute`. Standalone usage must pass it explicitly.

13. **`SandboxExecuteHandler` child handlers only receive `account_name`.** To prevent registry leak bugs, child tool calls inside `SandboxExecuteHandler.execute()` only pass `account_name` — no `registry` or extra `**context` kwargs are forwarded. This is intentional and prevents handlers from accidentally receiving the wrong registry.

## 12. Consumers

| Consumer | What it uses |
|----------|-------------|
| `src/container_config.py` | `HandlerRegistry`, `build_registry()` — creates `HandlerRegistryModule` for injector DI |
| `src/message_processors/function_calling_processor.py` | `HandlerRegistry` — calls `registry.tools()` for OpenAI tool definitions, `registry.create()` to execute tool calls |
| `src/message_processors/automation_processor.py` | `HandlerRegistry` — calls `registry.create()` during tasklist execution |
| `tests/test_chat2_handler.py` | `Chat2Handler` — direct unit tests |
| `tests/test_command_execution_handler2.py` | `CommandExecutionHandler2` — unit tests |
| `tests/test_execute_command_fail_fast.py` | `CommandExecutionHandler2` — fail-fast edge case tests |
| `tests/test_get_base_path_hanlder_utils.py` | `get_base_path` — unit tests |
| `tests/test_get_base_path_hybrid.py` | `get_base_path` — unit tests |
| `tests/test_tasklists_manage_handler.py` | `TasklistsManageHandler` — unit tests |
| `tests/test_tasklists_run_handler.py` | `TasklistsRunHandler` — unit tests |
| `_test_sandbox.py` | `SandboxExecuteHandler` — smoke tests for tool chaining, variable substitution, and `continue_on_error` |
