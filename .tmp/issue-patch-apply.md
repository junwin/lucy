## Summary

Add a new native `HandlerV2` tool, `patch_apply`, that applies a unified diff (`git apply`) to a file under a named storage/external location. This lets an agent modify a file by emitting only the changed hunks (a `.patch`) instead of writing the whole file via `file_save` — a large token/context win for big files with localized edits.

## Design

### Type

Native `HandlerV2` (subclass `HandlerV2` directly), following the `ResetSessionHandler` pattern. Not a galet adapter — it has its own apply logic. It reuses `LucyStorageLocationResolver` for location resolution (same as `FileSaveHandler2`).

### Files

- New: `src/handlers/patch_apply_handler.py`
- Edit: `src/handlers/registry_bootstrap.py` (import + register)
- Edit: `src/handlers/__init__.py` (export + `__all__`)
- New: `tests/test_patch_apply_handler.py`

### Tool definition (`tool_def`)

Name: `patch_apply`

Inputs (mirror `file_save`'s location scheme):

| arg | type | purpose |
|---|---|---|
| `location` | `"storage" \| "external"` | where the file lives |
| `external_root` | string | named external root when `location='external'`; else `''` |
| `path` | string | relative path to the file being patched |
| `patch_content` | string | unified diff text |
| `check_only` | boolean (default `false`) | validate without applying |

Required: `["location", "external_root", "path", "patch_content", "check_only"]`. `additionalProperties: false`, `strict: true`.

### Behavior (`execute`)

1. Resolve `base_dir` via `LucyStorageLocationResolver` (from `src.handlers.galet_adapters`), reusing the exact `location`/`external_root` rules from `FileSaveHandler2`:
   - `storage` → `storage_base_dir()` (reject non-empty `external_root`)
   - `external` → `external_root_dir(external_root)` (require `external_root`)
2. Reject absolute paths / drive letters / `..` segments — reuse `FileSaveHandler2._validate_and_normalize_relative_path` logic (copy the helper into the handler or factor it out).
3. Enforce realpath containment so the resolved target stays under `base_dir`.
4. Write `patch_content` to a temp file (e.g. `tempfile.NamedTemporaryFile(suffix=".patch")`).
5. Run from `base_dir` with `subprocess` (shell=False, list args):
   - `git apply --check <patchfile>`
   - if `check_only`, stop here and return `applied=false, ok=true` on success
   - else `git apply <patchfile>`
   - optionally `git apply --include=<path>` to restrict the patch to the single target file (defense-in-depth)
6. Return a structured result. Never raise on a bad patch — return `ok=false` with the `git apply` stderr as `error`.

### Return schema (`result_schema`)

```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean"},
    "tool": {"type": "string"},
    "applied": {"type": "boolean"},
    "location": {"type": "string"},
    "external_root": {"type": "string"},
    "path": {"type": "string"},
    "error": {"type": "string"}
  },
  "required": ["ok", "tool", "applied"]
}
```

### Execution contract

The tool executor calls `execute_raw(...)` when present. Implement both:

- `execute(args, *, account_name="auto", **context) -> Dict`
- `execute_raw(arguments_raw, *, account_name="auto", call_id="", **context) -> str` (JSON-parse args → `execute` → `json.dumps`)

Constructor is `__init__(self, config)` — the registry instantiates with `config`, same as `ResetSessionHandler`.

### Why `git apply`

- Works outside a git repo
- Handles `a/`/`b/` prefixes natively
- `--check` dry-run; `--reverse` for undo
- Fails atomically instead of guessing

## Registration

In `build_registry()`, import `PatchApplyHandler` and `reg.register(PatchApplyHandler)`. Export it in `src/handlers/__init__.py` and add to `__all__`.

## Tests

`tests/test_patch_apply_handler.py`, using `tmp_path` and `FakeConfig` (from `tests/conftest.py`) with `external_roots` pointing at a temp dir. Cover:

- applying a valid patch succeeds and modifies the file
- `check_only=True` validates without modifying
- invalid patch returns `ok=false` with error, file unchanged
- path traversal (`..`, absolute) rejected
- unknown `external_root` / wrong `location` rejected

## Acceptance criteria

- `patch_apply` is registered and discoverable
- `pytest tests/test_patch_apply_handler.py` passes
- No changes to existing handler files other than registration/export
- New handler does not modify `static/data/agents.json`
