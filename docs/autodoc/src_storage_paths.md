---
tags:
  - path
  - str
  - property
  - storage_path
  - module
  - storagepath
  - base
  - doc
  - source
  - resolver
  - src/storage_paths
---

# `src/storage_paths`

## Source files
- `src/storage_paths/storage_paths.py`

## Key classes
### `StoragePaths` (`src/storage_paths/storage_paths.py`)
Centralised, authoritative resolver for all user-data paths.

Key responsibilities:
- Resolves a **storage base** from `storage_root_path` + `storage_namespace`.
- Guards against namespace escaping the root (`ValueError` if misconfigured).
- Exposes domain base directories:
  - `contexts`, `chats`, `documents`, `tasklists`, `users`, `agents`
- Safely resolves user-supplied relative paths under the storage base.
- Builds **domain-local index paths** (indexes live inside each domain directory, not a top-level `indexes/`).

## Dependencies
- **stdlib:** `pathlib.Path`

## Methods (service/base class)
### `StoragePaths`
- `__init__(storage_root_path: str, storage_namespace: str)`
- `contexts(self) -> Path` *(property)*
- `chats(self) -> Path` *(property)*
- `documents(self) -> Path` *(property)*
- `tasklists(self) -> Path` *(property)*
- `users(self) -> Path` *(property)*
- `agents(self) -> Path` *(property)*
- `resolve_relative(self, relative_path: str) -> Path`
  - Resolves `(base / relative_path).resolve()` and rejects escapes outside `base`.
- `index_for(self, domain: str, account: str, filename: str = "index.json") -> Path`
  - Example: `index_for('chats', 'alice') -> <base>/chats/alice/index.json`
- `domain_index(self, domain: str, *subpaths: str) -> Path`
  - Flexible builder, e.g. `domain_index('documents', 'doc123', 'index.json')`.
