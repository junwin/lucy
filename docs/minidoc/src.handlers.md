---
tags:
  - Handler
  - HandlerV2
  - HandlerRegistry
  - FileLoadHandler2
  - FileSaveHandler
  - DelegateTasksHandler
  - ScrapeWebPageHandler2
  - CommandExecutionHandler2
  - WebSearchHandler2
  - GetKeywordsHandler
  - src.handlers
  - handlers
  - src.handlers
---

# src.handlers

Short description: Core tool handler layer for Lucy. Defines the handler interfaces and concrete tool implementations used by FunctionCallingProcessor and other components.

## Note on paths (important)

Many tools in this layer accept relative paths (for example `file_load`, `file_save`, and `execute_command.working_directory`).

By default, relative paths are resolved under the configured base for the chosen location (for example a Lucy "storage" namespace, or an allow-listed external root). When calling handlers from code that runs outside Lucy, choose the appropriate `location`/`external_root` values. When invoking tools from the FunctionCallingProcessor in tests or local automation, you will often use the repo prefix (e.g. `lucy/...`) via the `external` root.

Examples:
- location="storage" uses the configured storage base (storage_root_path + storage_namespace)
- location="external" uses a named external_root provided in config
- execute_command prefers location="sandbox" with working_directory relative to code_sandbox_path

## Handler contract (HandlerV2)

Handlers implement the HandlerV2 interface (src/handlers/handler_v2.py):
- classmethod name() -> str
- classmethod tool_def() -> Dict[str, Any]  (OpenAI-style function definition)
- classmethod result_schema() -> Optional[Dict[str, Any]]  (JSON schema for returned dict)
- execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]

Many handlers also expose execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str to support raw JSON string inputs/outputs for older callers.

## Registry (HandlerRegistry / registry_bootstrap)

- src/handlers/handler_registry.py
  - HandlerRegistry: register(handler_cls), create(name, *, config), tools(), tool_names(), result_schema(name), all_result_schemas()
  - At registration time the registry caches any non-None result_schema() returned by the handler class.

- src/handlers/registry_bootstrap.py
  - build_registry() imports and registers available HandlerV2 implementations.
  - Core handlers (expected available) are registered unconditionally.
  - Some handlers that depend on optional heavy dependencies or credentials are registered inside try/except blocks and will be skipped with a logged warning if unavailable (e.g., GetKeywordsHandler, WebSearchHandler2).

## Files / Handlers (current)

- src/handlers/__init__.py
  - Package init (no exported classes of note)

- src/handlers/handler.py
  - Legacy Handler interface (older code paths) with handle() and get_function_calling_definition(). New code should prefer HandlerV2.

- src/handlers/handler_v2.py
  - HandlerV2 (see contract above)

- src/handlers/schema_handler_v2.py
  - Helper utilities / shared JSON schema helpers used by handlers (inspect the file for details)

- src/handlers/handler_registry.py
  - HandlerRegistry (see Registry section)

- src/handlers/registry_bootstrap.py
  - build_registry() populates the registry with available handlers

- src/handlers/handler_utils.py
  - Helper utilities used by handlers (get_base_path, execute_script, etc.)

Concrete Handler implementations (HandlerV2) and notable details:

- src/handlers/file_load_handler2.py
  - Class: FileLoadHandler2
  - Tool name: "file_load"
  - Purpose: Safely read text files from named locations.
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Behavior: Enforces relative paths (no absolute paths or drive letters), validates no ".." segments, resolves base dir from config (storage_root_path + storage_namespace for location="storage", or external_roots[external_root] for location="external"), and ensures the resolved realpath is contained under the base directory before reading.
  - Tool parameters: location ("storage"|"external"), external_root, path

- src/handlers/file_save_handler.py
  - Class: FileSaveHandler2
  - Tool name: "file_save"
  - Purpose: Safely write text files to named locations.
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Behavior: Mirrors FileLoadHandler2 safety model; creates parent directories inside allowed base, enforces overwrite flag.
  - Tool parameters: location, external_root, path, file_content, overwrite

- src/handlers/command_execution_handler2.py
  - Class: CommandExecutionHandler2
  - Tool name: "execute_command"
  - Purpose: Run a command inside a sandboxed working directory under a named location.
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Behavior: Accepts location ("sandbox" or "external"), resolves working_directory relative to code_sandbox_path (or to an external_root), validates containment, runs subprocess with timeout and captures stdout/stderr. Truncates long output.
  - IMPORTANT: Commands are executed with shell=False (subprocess.run(..., shell=False)). Do NOT include shell operators or features (for example: |, &&, ||, ;, >, <, >>, 2>, $(...), backticks, variable expansion, globbing). If shell behavior is required, wrap the entire command in an explicit shell invocation such as `bash -lc '...'`. (bash is available in the environment.)
  - Tool parameters: location, external_root, command, working_directory, timeout_seconds

- src/handlers/scrape_web_page_handler2.py
  - Class: ScrapeWebPageHandler2
  - Tool name: "scrape_web_page"
  - Purpose: Scrape a web page by delegating to a utility script (python3 scrape.py ...).
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Behavior: Uses handler_utils.get_base_path and execute_script to run a scraper from a configured python_utils_path; returns scraped text.
  - Tool parameters: page_url

- src/handlers/web_search_handler2.py
  - Class: WebSearchHandler2
  - Tool name: "web_search_handler"
  - Purpose: Call the Brave Search API and return normalized results.
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Behavior / notes: Reads subscription key from a credentials file (config.credential_path/brave.json) at initialization. Because it requires credentials and network access, registry_bootstrap registers this handler inside a try/except and treats it as optional in some environments.
  - Tool parameters: query, count

- src/handlers/get_keywords_handler.py
  - Class: GetKeywordsHandler
  - Tool name: "get_keywords"
  - Purpose: Expose keyword extraction utilities (wraps src.keywords.keywords.Keywords).
  - Key methods: tool_def(), result_schema(), execute()
  - Notes: Depends on spaCy / NLTK / sklearn model/data availability. registry_bootstrap attempts to register this handler, but will log a warning and skip it if required NLP dependencies or models are missing.
  - Tool parameters: content, top_n, language_code

- src/handlers/delegate_tasks_handler.py
  - Class: DelegateTasksHandler
  - Tool name: "delegate_tasks"
  - Purpose: Produce a simple sequential task list (tasklist) from a high-level goal, optionally scoped to specific files. The handler only produces the plan; execution is performed by the orchestration layer.
  - Key methods: tool_def(), result_schema(), execute(), execute_raw()
  - Tool parameters: goal, files, instruction, worker_agent

## Optional / environment-dependent handlers

- GetKeywordsHandler (requires spaCy/nltk/sklearn and models/data)
- WebSearchHandler2 (requires Brave API credentials under credential_path)

These are registered in registry_bootstrap inside try/except blocks so that the registry can still be built in minimal environments.

## Other notes

- Many handlers set "strict": True in their tool_def, and list every property in the "required" array. Handlers implement small back-compat shims in execute_raw when appropriate (e.g., mapping legacy keys).
- HandlerRegistry caches result schemas at registration time when provided by handlers. This allows capability inspection without instantiating heavy dependencies later.

If you want me to expand any section (examples of tool_def shapes, sample calls, or add missing details), tell me which part to expand.
