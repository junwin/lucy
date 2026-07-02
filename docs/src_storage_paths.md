---
tags:
  - src_storage_paths
  - lucyproject
  - StoragePaths
  - resolve_relative
  - index_for
  - domain_index
---

## 1. Summary

`src/storage_paths` is a thin, single-class module that provides the **centralised, authoritative resolver for all user-data paths** in Lucy. It maps logical domains (`contexts`, `chats`, `documents`, `tasklists`, `users`, `agents`) to filesystem directories under a configurable storage root, and enforces a strict sandbox so that no caller can break out of the storage namespace via `..`, absolute paths, or symlink tricks.

It is the **single source of truth** for every on-disk location used by `JsonFileStorage` and related consumers. No other module should hard-code storage paths — they must always go through `StoragePaths`.

## 2. Architecture & Design

- **Single-class module.** Everything lives in one class `StoragePaths` — no inheritance, no ABC, no DI. It is a pure value object / path factory.
- **Sandboxed by construction.** The constructor resolves `storage_root_path` and `storage_namespace` into absolute `Path` objects, then checks `base.is_relative_to(root)`. If the namespace escapes (e.g. `storage_namespace = "../../outside"`), it raises `ValueError` immediately. This is a **hard guard against misconfiguration**.
- **No index directory.** Historically there was a top-level `indexes/` directory. That has been **removed** — index files now live alongside domain data (e.g. `chats/alice/index.json`). The `index_for()` and `domain_index()` helpers enforce this new convention.
- **Lazy properties.** The six domain properties (`contexts`, `chats`, `documents`, `tasklists`, `users`, `agents`) are simple `@property` accessors that return `Path` objects — they do not create directories on disk.
- **No configuration dependency.** `StoragePaths` does not read `ConfigManager`; it receives its two parameters as explicit constructor arguments. This keeps it testable with zero mocking.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `StoragePaths` | `object` | Centralised path resolver; owns all domain subdirectory paths and sandbox-safe relative resolution |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `storage_paths.py` | The entire module — class definition, properties, and helper methods | `StoragePaths` |

There is no `__init__.py`; the directory is a namespace package. The single file `storage_paths.py` is the module entry point.

## 5. Dependencies

### Standard library
- `pathlib.Path` — all path construction and resolution

### Third-party packages
- None

### Internal modules
- None — this is a leaf module with no internal dependencies

### Optional dependencies
- None

## 6. Configuration / Settings

**None.** `StoragePaths` does not read `ConfigManager`, env vars, or any config files. Its two parameters (`storage_root_path`, `storage_namespace`) are passed explicitly by the caller (typically `container_config.py`).

## 7. Exceptions

**None.** No custom exception classes are defined. The class raises stdlib `ValueError` for path escapes and invalid arguments.

## 8. Module-Level Constants

**None.** No module-level constants, defaults, or sentinels are defined.

## 9. Methods (by class)

### `StoragePaths`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, storage_root_path: str, storage_namespace: str) -> None` | Resolves `storage_root_path` and `storage_namespace` into absolute `Path` objects. Stores `.root` (resolved root) and `.base` (root/namespace, resolved). **Raises `ValueError`** if `base` is not relative to `root` (i.e. namespace escapes the root via `..` or absolute path). |
| `contexts` | property | `(self) -> Path` | Returns `<base>/contexts`. Does not create the directory. |
| `chats` | property | `(self) -> Path` | Returns `<base>/chats`. |
| `documents` | property | `(self) -> Path` | Returns `<base>/documents`. |
| `tasklists` | property | `(self) -> Path` | Returns `<base>/tasklists`. |
| `users` | property | `(self) -> Path` | Returns `<base>/users`. |
| `agents` | property | `(self) -> Path` | Returns `<base>/agents`. |
| `resolve_relative` | instance | `(self, relative_path: str) -> Path` | Safely resolves a user-supplied relative path under `self.base`. Joins, resolves (following symlinks), then checks `is_relative_to(base)`. **Raises `ValueError`** if the resolved path escapes the namespace — this catches absolute paths, `..` traversal, and symlink escapes. Returns the resolved `Path`. |
| `index_for` | instance | `(self, domain: str, account: str, filename: str = "index.json") -> Path` | Builds a canonical index path: `<base>/<domain>/<account>/<filename>`. Replace the old top-level `indexes/` directory. **Raises `ValueError`** if `domain` or `account` is empty. |
| `domain_index` | instance | `(self, domain: str, *subpaths: str) -> Path` | Flexible builder for domain-local paths. Joins `base / domain` with any number of `subpaths`. **Raises `ValueError`** if `domain` is empty. Example: `storage.domain_index('documents', 'doc123', 'index.json')` → `<base>/documents/doc123/index.json`. |

## 10. Usage Examples

**Construction and basic property access:**

```python
from src.storage_paths.storage_paths import StoragePaths

sp = StoragePaths("/data/lucy", "junwin")
print(sp.chats)       # /data/lucy/junwin/chats
print(sp.contexts)    # /data/lucy/junwin/contexts
print(sp.index_for("chats", "alice"))  # /data/lucy/junwin/chats/alice/index.json
```

**Safe relative path resolution:**

```python
# Resolves to /data/lucy/junwin/documents/report.txt
path = sp.resolve_relative("documents/report.txt")

# All of these raise ValueError:
sp.resolve_relative("/etc/passwd")       # absolute
sp.resolve_relative("../outside")        # parent traversal
sp.resolve_relative("link/secret.txt")   # symlink pointing outside
```

**Using in JsonFileStorage construction (real usage):**

```python
# From container_config.py
storage_paths = StoragePaths(
    storage_root_path=config.get("storage_root_path", "storage"),
    storage_namespace=config.get("storage_namespace", "default")
)
storage = JsonFileStorage(storage_paths)
```

## 11. Edge Cases & Gotchas

- **Path escape is caught at construction time**, not lazily. If `storage_namespace` is `"../../etc"`, the constructor raises `ValueError` immediately. This is a hard fail — no recovery.
- **`resolve_relative()` follows symlinks.** The method calls `Path.resolve()`, which resolves all symlinks in the chain. This is intentional; it prevents symlink-based escape attacks. A symlink inside the namespace that points outside will cause `resolve_relative()` to raise `ValueError`.
- **Properties do not create directories.** `sp.chats`, `sp.documents`, etc. return `Path` objects that may not exist on disk yet. Callers must `mkdir(parents=True)` before writing.
- **No `indexes` property.** The old top-level `indexes/` directory concept has been removed. Use `index_for()` or `domain_index()` to build domain-local index paths instead.
- **Empty domain/account raises `ValueError`** in `index_for()` and `domain_index()`. The checks are strict: empty string or None both trigger the error.
- **No `__init__.py`.** The package is a namespace package (no `__init__.py`). The import path is `from src.storage_paths.storage_paths import StoragePaths` — note the double `storage_paths`.
- **Thread-safe.** The class is immutable after construction (all attributes set in `__init__`, properties are pure read-only `Path` objects). No locks needed.
- **Tests cover all escape vectors:** absolute namespace, `..` traversal in namespace, absolute relative_path, `..` traversal in relative_path, and symlink escape.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/container_config.py` | Constructs `StoragePaths` with config values, passes to `JsonFileStorage` |
| `src/storage/json_file_storage.py` | Stores `self.storage_paths` and uses all properties (`.chats`, `.contexts`, `.documents`, `.tasklists`, `.users`, `.agents`, `.base`) plus `resolve_relative()` |
| `src/storage/json_file_storage_parts/chats.py` | Uses `.storage_paths.chats` for session I/O |
| `src/chat2/adapters/jfs_adapter.py` | Uses `storage.storage_paths.base / "chat2"` to build chat2 root |
| `src/handlers/chat2_handler.py` | Lazy-imports `StoragePaths` for session management helpers |
| `src/handlers/curate_chat_handler.py` | Lazy-imports `StoragePaths` in handler methods |
| `src/handlers/tasklists_manage_handler.py` | Imports `StoragePaths` at module level |
| `src/obsidian_index_cli.py` | Constructs `StoragePaths` and passes to `JsonFileStorage` |
| `tests/test_storage_paths.py` | Dedicated unit tests: constructor, properties, helpers, all escape guards |
| `tests/test_tasklists_storage.py` | Uses `StoragePaths(str(tmp_path), ns)` for tasklist test fixtures |
| `tests/chat2/test_jfs_adapter.py` | Uses `StoragePaths(str(tmp_path), "test_ns")` for adapter test fixtures |
