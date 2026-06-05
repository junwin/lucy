---
tags:
  - path
  - str
  - base
  - source
  - storage
  - root
  - chat
  - document
  - agent
  - account
  - src/storage_paths
  - lucyproject
---

# Module: `src/storage_paths`

## Key Class

**`StoragePaths`** — Centralised, authoritative resolver for all user-data paths. Index files are stored within each domain directory (e.g. `chats/<account>/index.json`) rather than a top-level `indexes` directory.

## Source Files

| File | Role |
|------|------|
| `storage_paths.py` | Single source file containing the `StoragePaths` class |

No `__init__.py` — the module is a single-file module.

## Dependencies

### Internal consumers (import `StoragePaths`)
- `src/obsidian_index_cli.py`
- `src/container_config.py`
- `src/storage/json_file_storage.py`
- `src/handlers/tasklists_manage_handler.py`

### External
- `pathlib.Path` (stdlib)

## Constructor

```python
def __init__(self, storage_root_path: str, storage_namespace: str)
```

Resolves `root` and `base` paths. Guards against namespace escaping `root` via `is_relative_to()` check.

## Properties (read-only, return `Path`)

| Property | Resolves to |
|----------|-------------|
| `contexts` | `base/contexts` |
| `chats` | `base/chats` |
| `documents` | `base/documents` |
| `tasklists` | `base/tasklists` |
| `users` | `base/users` |
| `agents` | `base/agents` |

## Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `resolve_relative` | `(relative_path: str) -> Path` | Safely resolve a user-supplied relative path under storage base. Rejects absolute paths, `..`, and symlink escapes. |
| `index_for` | `(domain: str, account: str, filename: str = "index.json") -> Path` | Canonical path for an index file within a domain/account subdirectory. Example: `index_for('chats', 'alice')` → `<base>/chats/alice/index.json` |
| `domain_index` | `(domain: str, *subpaths: str) -> Path` | Flexible builder for domain-local index paths with arbitrary subpath components. Example: `domain_index('documents', 'doc123', 'index.json')` → `<base>/documents/doc123/index.json` |
