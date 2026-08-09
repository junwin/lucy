```markdown
---
tags:
  - storage_paths
  - lucyproject
  - StoragePaths
---

## 1. Summary
The `storage_paths` module provides a centralized and authoritative resolver for user-data paths within a storage system. Its primary responsibility is to manage and construct file paths for various data types, such as contexts, chats, documents, task lists, skills, users, and agents, ensuring that all paths are correctly structured and secure. This module fits into the overall architecture by serving as a foundational component that other modules can rely on for consistent and safe path resolution, thereby solving the problem of path management and organization in a user-data context.

## 2. Architecture & Design
The design of the `StoragePaths` class employs several key principles:
- **Encapsulation**: The class encapsulates all logic related to path management, providing a clean interface for users to interact with.
- **Validation**: It includes robust validation to ensure that paths do not escape the defined storage root, preventing potential security issues.
- **Property Methods**: The use of property methods for common paths (e.g., `contexts`, `chats`, etc.) allows for a clean and intuitive API.

The class does not exhibit inheritance or complex relationships with other classes, as it stands alone in its functionality. There is no legacy or versioning split evident in the code, indicating a straightforward design focused on current requirements. Important design decisions include the rejection of absolute paths and symlink escapes, which are crucial for maintaining the integrity of the storage structure.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| StoragePaths  | None        | Manages and resolves user-data file paths.       |

## 4. Source Files
| File                        | Responsibility                                      | Notable Exports         |
|-----------------------------|----------------------------------------------------|-------------------------|
| `storage_paths.py`         | Defines the `StoragePaths` class for path management. | `StoragePaths`          |
| `__init__.py` (if present) | N/A — no additional exports.                       | None                    |

## 5. Dependencies
- **Standard library**:
  - `pathlib`: Used for path manipulations and validations.
  
- **Third-party packages**: None.

- **Internal modules**: None.

- **Optional dependencies**: None.

## 6. Configuration / Settings
None.

## 7. Exceptions
| Exception      | Base         | When Raised                                      |
|----------------|--------------|--------------------------------------------------|
| ValueError     | Exception    | Raised when paths escape the defined storage root or when required parameters are missing. |

## 8. Module-Level Constants
None.

## 9. Methods (by class)

### StoragePaths
| Method              | Type         | Signature                                         | Description                                                                                       |
|---------------------|--------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `__init__`          | Instance     | `def __init__(self, storage_root_path: str, storage_namespace: str)` | Initializes the `StoragePaths` object, setting the root and namespace, and validates the configuration. |
| `contexts`          | Property     | `def contexts(self) -> Path`                      | Returns the path for contexts.                                                                    |
| `chats`             | Property     | `def chats(self) -> Path`                         | Returns the path for chats.                                                                       |
| `documents`         | Property     | `def documents(self) -> Path`                     | Returns the path for documents.                                                                    |
| `tasklists`         | Property     | `def tasklists(self) -> Path`                     | Returns the path for task lists.                                                                   |
| `skills`            | Property     | `def skills(self) -> Path`                        | Returns the path for skills.                                                                       |
| `users`             | Property     | `def users(self) -> Path`                         | Returns the path for users.                                                                        |
| `agents`            | Property     | `def agents(self) -> Path`                        | Returns the path for agents.                                                                       |
| `resolve_relative`  | Instance     | `def resolve_relative(self, relative_path: str) -> Path` | Safely resolves a user-supplied relative path under the storage base, rejecting unsafe paths.     |
| `index_for`         | Instance     | `def index_for(self, domain: str, account: str, filename: str = "index.json") -> Path` | Returns the canonical path for an index file for a given domain and account.                      |
| `domain_index`      | Instance     | `def domain_index(self, domain: str, *subpaths: str) -> Path` | Builds domain-local index paths, allowing for flexible path construction.                         |

## 10. Usage Examples
```python
from storage_paths import StoragePaths

# Initialize the StoragePaths with a root and namespace
storage = StoragePaths("/data/storage", "user_data")

# Access specific paths
chat_path = storage.chats
index_path = storage.index_for("chats", "alice")
```

## 11. Edge Cases & Gotchas
- The `StoragePaths` class employs a fail-fast approach by raising `ValueError` exceptions when invalid paths are provided or when required parameters are missing.
- The class does not handle legacy field mapping or backward compatibility, as it appears to be designed for current use cases only.
- There are no explicit thread-safety concerns mentioned, but users should be aware of potential issues if multiple threads modify paths concurrently.

## 12. Consumers
| Consumer         | What it uses                                   |
|------------------|------------------------------------------------|
| Unknown          | Unknown — trace imports to confirm.            |
```