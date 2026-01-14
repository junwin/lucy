---
tags:
  - storage_paths
  - StoragePaths
  - paths
  - storage
---

# storage_paths

Short description: Centralised, authoritative resolver for all user-data paths under a configured storage root + namespace.

## Python files and key classes

- `StoragePaths` — `src/storage_paths/storage_paths.py`

## Notes

- `StoragePaths(storage_root_path, storage_namespace)` builds:
  - `root`: resolved `Path(storage_root_path)`
  - `base`: resolved `root / storage_namespace`

- Hard guard: raises `ValueError` if `storage_namespace` would escape `storage_root_path`.

- Provides standard subdirectories as properties:
  - `contexts`, `chats`, `documents`, `users`, `agents`

- `resolve_relative(relative_path)` safely resolves a user-supplied path under `base`:
  - rejects escapes via `..`, absolute paths, or symlink tricks
  - raises `ValueError("Path escapes storage namespace")` if the resolved path is outside `base`

- Index files are no longer provided as a single global/top-level `indexes` directory. Instead, indexes are maintained per domain (domain-local index pattern). For example, a chat/account index would live under that domain's directory (e.g., `chats/<account>/index.json`). Callers and tests should reference domain-local index files rather than a global `StoragePaths.indexes` property.

## Related docs

- See `docs/minidoc/src.handlers.md` for the *tool-facing* path rules (how `file_load`, `file_save`, and `execute_command` interpret `location`, `external_root`, and relative paths).
