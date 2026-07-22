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
| StoragePaths  | None        | Manages and resolves user-data paths securely.    |

## 4. Source Files
| File                        | Responsibility                                      | Notable Exports       |
|-----------------------------|----------------------------------------------------|-----------------------|
| `storage_paths.py`         | Defines the `StoragePaths` class for path management. | `StoragePaths`        |
| `__init__.py` (if present) | N/A — no `__init__.py` file present.              | None                  |

## 5. Dependencies
- **Standard library**:
  - `pathlib`: Used for path manipulations.
  
- **Third-party packages**: None.

- **Internal modules**: None.

- **Optional dependencies**: None.

## 6. Configuration / Settings
None.

## 7. Exceptions
| Exception      | Base         | When Raised                                      |
|----------------|--------------|--------------------------------------------------|
| ValueError     | Exception    | Raised when paths escape the defined storage structure. |

## 8. Module-Level Constants
None.

## 9. Methods (by class)

### StoragePaths
| Method               | Type         | Signature                                         | Description                                                                                       |
|----------------------|--------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `__init__`           | Instance     | `def __init__(self, storage_root_path: str, storage_namespace: str)` | Initializes the `StoragePaths` object, setting the root and namespace, and validating the configuration. Raises `ValueError` if the namespace escapes the root path. |
| `contexts`           | Property     | `def contexts(self) -> Path`                      | Returns the path for the contexts directory within the storage namespace.                        |
| `chats`              | Property     | `def chats(self) -> Path`                         | Returns the path for the chats directory within the storage namespace.                           |
| `documents`          | Property     | `def documents(self) -> Path`                     | Returns the path for the documents directory within the storage namespace.                       |
| `tasklists`          | Property     | `def tasklists(self) -> Path`                     | Returns the path for the tasklists directory within the storage namespace.                       |
| `skills`             | Property     | `def skills(self) -> Path`                        | Returns the path for the skills directory within the storage namespace.                          |
| `users`              | Property     | `def users(self) -> Path`                         | Returns the path for the users directory within the storage namespace.                           |
| `agents`             | Property     | `def agents(self) -> Path`                        | Returns the path for the agents directory within the storage namespace.                          |
| `resolve_relative`    | Instance     | `def resolve_relative(self, relative_path: str) -> Path` | Safely resolves a user-supplied relative path under the storage base, rejecting absolute paths and symlink escapes. Raises `ValueError` if the path escapes the namespace. |
| `index_for`          | Instance     | `def index_for(self, domain: str, account: str, filename: str = "index.json") -> Path` | Returns the canonical path for an index file for a given domain and account. Raises `ValueError` if domain or account is not provided. |
| `domain_index`       | Instance     | `def domain_index(self, domain: str, *subpaths: str) -> Path` | Builds a flexible domain-local index path. Raises `ValueError` if the domain is not provided. |

## 10. Usage Examples
```python
from storage_paths import StoragePaths

# Initialize the StoragePaths with a root and namespace
storage = StoragePaths("/data/storage", "user_data")

# Access the path for user contexts
contexts_path = storage.contexts

# Resolve a relative path safely
resolved_path = storage.resolve_relative("chats/alice/messages.json")
```

## 11. Edge Cases & Gotchas
- The `resolve_relative` method is designed to be robust against various path manipulation techniques, ensuring that users cannot escape the defined storage namespace.
- The class does not handle multi-threading concerns, so users should ensure that instances are not shared across threads without proper synchronization.
- The design assumes that the provided `storage_root_path` and `storage_namespace` are valid and correctly formatted.

## 12. Consumers
| Consumer         | What it uses                                   |
|------------------|------------------------------------------------|
| Unknown          | Unknown — trace imports to confirm.            |
```