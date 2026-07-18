---
tags:
  - src_storage_paths
  - lucyproject
  - StoragePaths
  - path
  - resolver
  - domain
  - account
  - index
  - storage_root
  - namespace
---

# Module: `src.storage_paths`

## Summary

Centralised, authoritative path resolver for all user-data directories. Maps logical domains (chats, contexts, documents, tasklists, skills, users, agents) to filesystem paths under a configurable storage root and namespace. Includes safety guards against path traversal and symlink escapes.

## Key Classes

| Class | Purpose |
|---|---|
| `StoragePaths` | Path resolver — provides property-based access to domain directories and safe `resolve_relative()` for user-supplied paths. |

## Source Files

| File | Description |
|---|---|
| `storage_paths.py` | Single-file module containing the `StoragePaths` class. No `__init__.py` (package is implicit). |

## Dependencies

- **Standard library**: `pathlib.Path`
- **Internal consumers**: `src.storage.json_file_storage`, `src.container_config`, `src.handlers.tasklists_manage_handler`, `src.obsidian_index_cli`

## Methods — `StoragePaths`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | constructor | `(storage_root_path: str, storage_namespace: str) -> None` | Resolve root and namespace; guard against namespace escaping root. |
| `contexts` | `@property` | `() -> Path` | Path to `contexts/` directory. |
| `chats` | `@property` | `() -> Path` | Path to `chats/` directory. |
| `documents` | `@property` | `() -> Path` | Path to `documents/` directory. |
| `tasklists` | `@property` | `() -> Path` | Path to `tasklists/` directory. |
| `skills` | `@property` | `() -> Path` | Path to `skills/` directory. |
| `users` | `@property` | `() -> Path` | Path to `users/` directory. |
| `agents` | `@property` | `() -> Path` | Path to `agents/` directory. |
| `resolve_relative` | instance | `(relative_path: str) -> Path` | Safely resolve a user-supplied relative path under storage base; rejects absolute paths, `..`, and symlink escapes. |
| `index_for` | instance | `(domain: str, account: str, filename: str = "index.json") -> Path` | Canonical path for a domain+account index file (e.g. `chats/alice/index.json`). |
| `domain_index` | instance | `(domain: str, *subpaths: str) -> Path` | Flexible builder for domain-local index paths with arbitrary subpath components. |
