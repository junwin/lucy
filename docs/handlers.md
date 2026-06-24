# Handlers

This repo exposes "tools" to the LLM via the **handlers** module (`src/handlers`).

A handler is a small, pluggable unit that:

- advertises a tool definition (name/description/parameters)
- executes some side-effectful or external operation
- returns a structured result

There are currently **two handler styles** in the codebase:

1. **`HandlerV2`**: the original v2 interface (dict-in / dict-out)
2. **`SchemaHandlerV2`**: a newer typed base (raw-JSON-in / JSON-string-out) using Pydantic models

The registry (`HandlerRegistry`) is still built around `HandlerV2`, but `SchemaHandlerV2` exists for incremental migration.

---

## Directory overview

`src/handlers/`

- `handler_v2.py` – `HandlerV2` abstract base class
- `schema_handler_v2.py` – `SchemaHandlerV2` typed base class (Pydantic)
- `handler_registry.py` – `HandlerRegistry` (register/create/tools/result schemas)
- `registry_bootstrap.py` – `build_registry()` that registers concrete handlers
- `handler_utils.py` – shared helpers (safe base-path resolution, script execution, etc.)

Concrete handlers (tools):

- `file_load_handler2.py` – `file_load`
- `file_save_handler.py` – `file_save`
- `command_execution_handler2.py` – `execute_command`
- `scrape_web_page_handler2.py` – `scrape_web_page`
- `web_search_handler2.py` – `web_search`
- `get_keywords_handler.py` – `get_keywords` (optional deps)
- `delegate_tasks_handler.py` – `delegate_tasks`

---

## HandlerV2 (dict-in / dict-out)

File: `src/handlers/handler_v2.py`

`HandlerV2` is the "classic" tool interface:

- `@classmethod def name(cls) -> str`
- `@classmethod def tool_def(cls) -> Dict[str, Any]`
- `@classmethod def result_schema(cls) -> Optional[Dict[str, Any]]` (optional)
- `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]`

Notes:

- `tool_def()` returns an OpenAI-style tool definition:
  - `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}`
- `execute()` returns a Python `dict` (the tool result).

---

## SchemaHandlerV2 (typed, raw JSON interface)

File: `src/handlers/schema_handler_v2.py`

`SchemaHandlerV2` is a newer base class intended to make tool calls more robust by:

- validating arguments with a Pydantic `ArgsModel`
- validating results with a Pydantic `ResultModel`
- standardizing error codes
- providing a raw JSON-string interface (`execute_raw`) that always returns a JSON object string

Key pieces:

- `ArgsModel: Type[pydantic.BaseModel]`
- `ResultModel: Type[pydantic.BaseModel]`
- `@classmethod def name(cls) -> str`
- `@classmethod def tool_def(cls) -> Dict[str, Any]`
- `def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str`
- `def execute(self, args: ArgsModel, *, account_name: str = "auto", call_id: str = "") -> ResultModel | Dict[str, Any]`

Shared error codes (enum `ErrorCode`):

- `invalid_args`
- `tool_execution_failed`
- `result_serialization_failed`

`SchemaHandlerV2.result_schema()` defaults to `ResultModel.model_json_schema()` when available.

---

## HandlerRegistry

File: `src/handlers/handler_registry.py`

`HandlerRegistry` is the central registry for `HandlerV2` implementations.

What it does:

- maps `handler_name -> handler_class`
- prevents empty names and duplicate registrations
- caches `result_schema()` at registration time (best-effort)

Key methods:

- `register(handler_cls)`
- `create(name: str, *, config) -> HandlerV2`
- `tools() -> List[tool_def]`
- `tool_names() -> List[str]` (sorted)
- `result_schema(name)` / `all_result_schemas()`

Important detail:

- `create()` currently assumes all `HandlerV2` handlers accept `config` in `__init__`.

---

## Registry bootstrap

File: `src/handlers/registry_bootstrap.py`

`build_registry()` constructs a registry and registers handlers.

Currently registered:

Core (expected):

- `FileLoadHandler2` (`file_load`)
- `FileSaveHandler2` (`file_save`)
- `CommandExecutionHandler2` (`execute_command`)
- `ScrapeWebPageHandler2` (`scrape_web_page`)

Optional:

- `WebSearchHandler2` (`web_search`) – registered in a try/except
- `GetKeywordsHandler` (`get_keywords`) – registered in a try/except; may require spaCy/nltk/scikit-learn

Also registered:

- `DelegateTasksHandler` (`delegate_tasks`)

---

## Example: execute_command

File: `src/handlers/command_execution_handler2.py`

Purpose: execute an OS command in a controlled working directory.

Typical parameters:

- `location`: `"sandbox" | "external"`
- `external_root`: name of the external root when `location="external"`
- `command`: full command line (executed with shell=False; see WARNING below)
- `working_directory`: relative directory under the chosen root
- `timeout_seconds`: execution timeout

WARNING (important): the handler executes commands with shell=False (subprocess.run(..., shell=False)). Do NOT use shell operators (examples include: &&, ||, |, ;, >, <, >>, 2>, subshells, backticks, etc.) in the `command` string. If you require shell behavior (pipes, redirection, compound/conditional commands), wrap the whole command in a shell invocation. Example wrapper to allow pipes/redirection:

```
command: "bash -lc 'grep -R \"pattern\" . | sed -n \"1,10p\"'"
```

(For now, bash is available in the environment.)

The handler:

- resolves a safe base path (via `handler_utils.get_base_path(...)`)
- runs the command with `subprocess.run(..., shell=False)`
- returns a structured dict including `ok`, `returncode`, `stdout`, `stderr`


Note: the execute_command handler now does fail-fast detection of a small set of shell-only syntax to prevent accidental hangs or unintended shell behavior when callers pass shell syntax directly. The simplest safe rule is applied:

- Detect heredoc operators (`<<`) and reject when present in the raw `command` string, unless the command is explicitly wrapped with an allowed shell wrapper. This prevents cases where an unwrapped heredoc would block waiting for input.
- Other shell operators (pipes `|`, redirection `>`, `<`, `>>`, logical operators `&&`, `||`, command separators `;`, subshells `$()`, backticks) may also be detected and rejected.

To avoid false positives the detection is intentionally minimal and conservative:

- If the command begins with an allowed wrapper (for example `bash -lc ` or `sh -lc `), the handler will not reject the command even if it contains shell syntax. This permits legitimate uses that intentionally run a shell.
- Detection looks for the heredoc token `<<` outside of a recognized wrapper; it does not attempt full shell parsing. As a result it avoids flagging common benign strings.

If a caller receives a failure due to detected shell syntax, the recommended fix is to wrap the intended command in a shell invocation, e.g.:

```
command: "bash -lc 'printf \"line1\\nline2\\n\" | grep line'"
```

or, for heredoc usage specifically:

```
command: "bash -lc 'cat <<EOF\\nhello\\nEOF\\n'"
```

This rule is intended to be the simplest safe guard against accidental hangs (heredoc) while allowing explicit shell usage via wrappers. The detection is purposely minimal to avoid false positives for wrapped commands or for strings that merely contain `<<` in non-shell contexts.
---

## Path safety model (important)

Several handlers accept file paths or working directories.

The safety model is:

- paths are **relative** to a configured base directory
- no absolute paths
- no `..` traversal

This is enforced by the file and command handlers (and by `handler_utils.get_base_path`).

---

## When to use which base class

- Use **`HandlerV2`** when you want the simplest implementation and you're OK with "best effort" validation.
- Use **`SchemaHandlerV2`** when you want strict argument/result validation and standardized error handling.

If you want, I can also update this doc to include a short per-tool table of parameters and result fields for each concrete handler (based on the current code).
