# Handlers (v2)

## What is a handler?

A **HandlerV2** is a pluggable "tool implementation" that the AI can call. Each handler:

1. **Defines a tool** (for OpenAI / function calling):
   - `@classmethod def tool_def(cls) -> Dict[str, Any]`
   - Returns an OpenAI-style tool definition:
     - `type: "function"`
     - `function: { name, description, parameters (JSON schema) }`
   - This is what gets exposed to the model as an available tool.

2. **Has a stable name**:
   - `@classmethod def name(cls) -> str`
   - Used as the tool/function name and as the key in the registry.

3. **Executes the tool logic**:
   - `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]`
   - Takes structured arguments (matching `tool_def.parameters`).
   - Returns a **structured Python dict** with the result (and error info if needed).

4. **Optionally defines a result schema**:
   - `@classmethod def result_schema(cls) -> Optional[Dict[str, Any]]`
   - JSON schema describing the shape of the dict returned by `execute`.
   - Used by `HandlerRegistry` to collect schemas.

5. **May provide a helper for tool content** (not in the base interface, but used in examples):
   - `execute_as_tool_content(...) -> str`
   - Wraps `execute` and returns JSON-serialized string, suitable for tool output.

So conceptually:

> A handler is a pluggable "tool implementation" that:
> - advertises itself via a tool definition (name, description, parameters),
> - runs some side-effectful or external operation when called,
> - and returns a structured result dict, optionally described by a JSON schema.

## HandlerRegistry

`HandlerRegistry` is the central registry for all `HandlerV2` implementations:

- Keeps a mapping: `handler_name -> handler_class`.
- Ensures:
  - `name()` is non-empty.
  - No duplicate names.

Key methods:

- `register(handler_cls: Type[HandlerV2])`  
  Register a handler class.

- `create(name: str, *, config: ConfigManager) -> HandlerV2`  
  Instantiate a handler by name, passing a `ConfigManager` into its constructor.

- `tools() -> List[Dict[str, Any]]`  
  Returns all `tool_def()`s for registered handlers (for exposing to the LLM).

- `tool_names() -> List[str]`  
  Sorted list of handler names.

- `result_schema(name: str)` and `all_result_schemas()`  
  Access the JSON schemas for handler results.

So the registry is the glue that:

- Knows which handlers exist.
- Can create them with config.
- Can provide their tool definitions and result schemas to the rest of the system.

## Examples

### CommandExecutionHandler2

File: `src/handlers/command_execution_handler2.py`

**Purpose:** Execute an OS command in a given working directory under a controlled base folder.

Key points:

- `NAME = "execute_command"`.
- `tool_def()` describes parameters: `command`, `working_directory`, `timeout_seconds`.
- `execute()`:
  - Validates inputs.
  - Uses `get_base_path(config, account_name, working_directory)` to resolve a safe directory.
  - Runs the command with `subprocess.run` (`shell=False`).
  - Returns a structured result dict with `ok`, `returncode`, `stdout`, `stderr`, and a human-friendly `result`.

### ScrapeWebPageHandler2

File: `src/handlers/scrape_web_page_handler2.py`

**Purpose:** Read the text from a webpage by calling an external Python script.

Key points:

- `NAME = "scrape_web_page"`.
- `tool_def()` describes parameter: `page_url`.
- `execute()`:
  - Validates `page_url`.
  - Reads `python_utils_path` from `ConfigManager`.
  - Resolves `base_path = get_base_path(config, account_name, python_utils_path)`.
  - Builds command: `python3 scrape.py {page_url}`.
  - Calls `execute_script(command, base_path)`.
  - Returns a structured result dict with `ok`, `page_url`, `result` (scraped text) or `error`.

## Dependencies of a handler

From these examples, a typical `HandlerV2` depends on:

### Core interface

- `src.handlers.handler_v2.HandlerV2` – abstract base class defining `name`, `tool_def`, `result_schema`, and `execute`.

### Configuration

- `src.config_manager.ConfigManager` – passed into the handler constructor and used to read configuration values.

### Handler utilities

- `src.handlers.handler_utils.get_base_path(config, account_name, relative_path)` – resolves a relative path into a safe, allowed base directory.
- `src.handlers.handler_utils.execute_script(command, base_path)` – helper to run a command in a given base path and return its output (used by some handlers).

### Standard library / logging

- `os`, `shlex`, `subprocess`, `logging`, `json`, `typing` (`Dict`, `Any`, etc.).

### Registry

- `src.handlers.handler_registry.HandlerRegistry` – used by the system to register handlers, instantiate them with config, and expose their tool definitions and result schemas.
