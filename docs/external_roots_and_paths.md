# External roots and path handling (Lucy tools)

This document explains how Lucy’s file and command tools resolve paths after the recent path-handling changes.

## Summary

Several handlers now require an `external_roots` mapping in config and enforce **safe, relative paths**.

Key rules:

- Tool calls **must not** use absolute paths.
- Tool calls **must not** contain `..` path segments.
- When using `location="external"`, you must provide an `external_root` key and a **relative** `path`/`working_directory` under that root.
- When using `location="storage"` or `location="sandbox"`, `external_root` must be the empty string (`""`).

Affected handlers:

- `src/handlers/file_load_handler2.py`
- `src/handlers/file_save_handler.py`
- `src/handlers/command_execution_handler2.py`

## Configuration: `external_roots`

These handlers expect a config entry like:

```json
{
  "external_roots": {
    "repo_lucy": "/home/junwin/src/repos/lucy",
    "repos": "/home/junwin/src/repos",
    "obsidian": "/home/junwin/obsidian/test",
    "sandbox_cmd": "/home/junwin/sandbox"
  }
}
```

- `external_root` in a tool call must be one of the keys in `external_roots`.
- The handler resolves the base directory from this mapping and then joins it with the provided relative path.

## Path rules (applies to `path` and `working_directory`)

All three handlers apply similar safety checks:

1. **Relative only**
   - Absolute paths are rejected (e.g. `/home/...`).
   - Windows drive-letter paths are rejected (e.g. `C:\\...`).

2. **No parent traversal**
   - Any `..` segment is rejected.

3. **No escaping the base directory**
   - The handler uses `realpath` and checks the resolved target stays inside the resolved base directory.
   - This prevents escaping via symlinks.

## Tool-specific behavior

### `file_load` (`FileLoadHandler2`)

**Inputs**

- `location`: `"storage"` or `"external"`
- `external_root`: required by schema (use `""` for storage)
- `path`: relative path

**Notes**

- Runtime compatibility: the handler also accepts `relative_path` as an alias for `path`, but new calls should use `path`.
- For `location="external"`, `external_root` must be non-empty and present in `external_roots`.
- The target must exist and be a file.

**Example (load from this repo)**

```json
{
  "location": "external",
  "external_root": "repo_lucy",
  "path": "src/handlers/file_load_handler2.py"
}
```

### `file_save` (`FileSaveHandler2`)

**Inputs**

- `location`: `"storage"` or `"external"`
- `external_root`: required by schema
- `path`: relative path
- `file_content`: string
- `overwrite`: boolean

**Notes**

- Runtime compatibility: `relative_path` may be mapped to `path` if `path` is missing.
- If `location="storage"`, `external_root` must be `""`.
- If `location="external"`, `external_root` must be set and present in `external_roots`.
- Parent directories are created under the base directory.
- If `overwrite=false` and the file exists, the write fails.

**Example (save into this repo)**

```json
{
  "location": "external",
  "external_root": "repo_lucy",
  "path": "docs/notes/example.md",
  "file_content": "Hello",
  "overwrite": true
}
```

### `execute_command` (`CommandExecutionHandler2`)

**Inputs**

- `location`: `"sandbox"` or `"external"`
- `external_root`: required by schema (use `""` for sandbox)
- `command`: string (executed with `shell=false`)
- `working_directory`: relative directory under the base
- `timeout_seconds`: integer

**Important - shell behavior and restrictions**

- Commands are executed with `shell=False` using `shlex.split` and `subprocess.run(..., shell=False)`.
- Do NOT use shell operators directly in the `command` string. Examples of operators and shell features that will NOT work unless you run a shell include:
  - Pipes and filters: `|`
  - Conditional/compound operators: `&&`, `||`, `;`
  - Redirection: `>`, `>>`, `<`, `2>`, `2>&1`
  - Subshells and command substitution: `$(...)`, backticks `` `...` ``
  - Variable expansion, globbing and other shell parsing features
- If you need shell features (pipes, redirection, compound commands), wrap the entire command in an explicit shell invocation. For example:

```json
{
  "location": "external",
  "external_root": "repo_lucy",
  "command": "bash -lc 'grep -R \"pattern\" . | sed -n \"1,10p\"'",
  "working_directory": "src",
  "timeout_seconds": 30
}
```

- Note: at present bash is available in the environment; use `bash -lc '...'` to enable shell features.

**Notes**

- If `location="sandbox"`, the base directory is `config["code_sandbox_path"]` (and may be further scoped by `account_name` if that directory exists).
- If `location="external"`, the base directory is `external_roots[external_root]`.
- `working_directory` must exist and be a relative path under the chosen base.

**Example (run a command in this repo)**

```json
{
  "location": "external",
  "external_root": "repo_lucy",
  "command": "python -m pytest -q",
  "working_directory": "src",
  "timeout_seconds": 30
}
```

> Note: some handlers reject `"."` as a working directory because it is not treated as a “safe relative path” in their validation. If you hit that error, use an explicit subdirectory that exists (e.g. `"src"`) or adjust the validation rules.

## Common failure modes

- **"path must be relative"**: you passed an absolute path.
- **".. is not allowed"**: you used parent traversal.
- **"unknown external_root"**: the key is not present in `external_roots`.
- **"resolved path escapes base"**: the path (or a symlink) points outside the base directory.
- **"working_directory does not exist"**: the directory is missing under the base.

## Recommended conventions

- Prefer `external_root="repo_lucy"` for operations within the Lucy repo.
- Keep tool calls consistent: always use `path` (not `relative_path`).
- Use `location="storage"` only for Lucy-managed storage; use `location="external"` for real filesystem access.
