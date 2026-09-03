# Module Documentation for `src/http_endpoints`

## YAML Front Matter
```yaml
tags:
  - src_http_endpoints
  - lucyproject
  - AgentManager
  - Chat2Store
  - ChatEvent
  - DocumentStore
  - MetricsRepository
  - PromptBuilder
```

## 1. Summary
The `src/http_endpoints` module provides a set of HTTP endpoint implementations for managing various functionalities related to agents, chats, documents, metrics, and task lists. It serves as a bridge between client requests and the underlying business logic, facilitating operations such as creating, retrieving, updating, and deleting resources. This module fits into the overall architecture as a critical component for handling HTTP requests and responses, ensuring that the application can interact with external clients effectively. It solves the problem of exposing a RESTful API for various functionalities, allowing clients to perform operations on agents, chats, documents, and metrics seamlessly.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: Many endpoints utilize dependency injection to obtain instances of services like `AgentManager`, `Chat2Store`, and `MetricsRepository`, promoting loose coupling and easier testing.
- **Error Handling**: Each endpoint implementation includes robust error handling, logging exceptions, and returning appropriate HTTP status codes and error messages.

Classes within the module often interact through composition, where endpoint functions depend on services provided by other modules. For instance, chat-related endpoints rely on `Chat2Store` for data management, while document endpoints utilize `DocumentStore`. The design avoids legacy code by focusing on a unified approach to handling requests, ensuring that older versions of storage (like v1) are not used.

Important design decisions include:
- The use of structured error responses to provide clarity to clients.
- The separation of concerns, where each endpoint is responsible for a specific resource type.

## 3. Key Classes
| Class          | Base/Parent | Purpose                                      |
|----------------|-------------|----------------------------------------------|
| AgentManager   | None        | Manages agent-related operations.            |
| Chat2Store     | None        | Handles storage and retrieval of chat sessions. |
| ChatEvent      | None        | Represents events in a chat session.        |
| DocumentStore  | None        | Manages document storage and retrieval.     |
| MetricsRepository | None    | Handles metrics data storage and retrieval. |
| PromptBuilder  | None        | Constructs prompts based on input parameters. |

## 4. Source Files
| File                             | Responsibility                                      | Notable Exports                      |
|----------------------------------|----------------------------------------------------|-------------------------------------|
| agents_endpoints.py              | Manages agent-related HTTP endpoints.               | get_agents_impl, list_context_names_impl |
| chats_endpoints.py               | Manages chat session-related HTTP endpoints.        | post_chat_impl, get_chats_impl     |
| context_endpoints.py             | Manages context-related HTTP endpoints.             | list_context_names_impl             |
| documents_endpoints.py           | Manages document-related HTTP endpoints.            | search_documents_impl                |
| metrics_endpoints.py             | Manages metrics-related HTTP endpoints.             | get_metrics_runs_impl               |
| prompt_and_docs_endpoints.py     | Manages prompt and document-related HTTP endpoints. | build_prompt_impl, search_documents_impl |
| prompt_builder_debug_endpoints.py | Provides debugging for prompt builder.              | prompt_builder_debug_impl            |
| prompt_builder_endpoints.py      | Manages prompt building HTTP endpoints.             | build_prompt_impl                   |
| prompt_builder_metrics_endpoints.py | Provides metrics for prompt building.              | prompt_builder_metrics_impl          |
| tasklist_endpoints.py            | Manages task list-related HTTP endpoints.           | list_tasklists_impl, get_tasklist_impl |
| upload_endpoints.py              | Manages file upload HTTP endpoints.                 | post_upload_image_impl              |
| __init__.py                      | Initializes the module and exports key functions.  | Various endpoint functions           |

## 5. Dependencies
- **Standard library**:
  - `logging`
  - `json`
  - `os`
  - `uuid`
  - `datetime`
  - `typing`
  
- **Third-party packages**:
  - None

- **Internal modules**:
  - `src.agent`
  - `src.chat2.facade`
  - `src.chat2.models`
  - `src.storage.interfaces`
  - `src.metrics`
  - `src.prompt_builders.prompt_builder`
  - `src.config_manager`
  - `src.utils.document_context`
  - `src.utils.text_snippet_loader`
  - `src.keywords.keywords`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                          | Type   | Default                       | What it controls                          |
|------------------------------|--------|-------------------------------|-------------------------------------------|
| storage_root_path            | str    | /home/junwin/lucy_storage    | Base path for storage operations.         |
| storage_namespace             | str    | data                          | Namespace for storage operations.         |
| max_upload_size_bytes        | int    | 10485760 (10 MB)             | Maximum allowed upload size for files.   |
| metrics_runs_log_path        | str    | metrics/runs.jsonl           | Path for metrics runs log.               |

## 7. Exceptions
| Exception                    | Base         | When Raised                                      |
|------------------------------|--------------|-------------------------------------------------|
| None                         | None         | No custom exceptions defined in this module.    |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| ALLOWED_IMAGE_MIME_TYPES     | {"image/png", "image/jpeg", "image/gif", "image/webp"} |
| EXT_BY_MIME                  | {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"} |

## 9. Methods (by class)
### AgentManager
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### Chat2Store
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### ChatEvent
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### DocumentStore
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### MetricsRepository
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### PromptBuilder
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| N/A    | N/A         | N/A       | N/A         |

### TaskList CRUD Implementations
| Method | Type        | Signature | Description |
|--------|-------------|-----------|-------------|
| list_tasklists_impl | instance | (storage, account_name: str) -> Tuple[Any, int] | Lists all task lists for a given account. Returns a list of task list IDs or an error. |
| get_tasklist_impl | instance | (storage, account_name: str, tasklist_key: str) -> Tuple[Any, int] | Retrieves a specific task list by key. Returns the task list or an error if not found. |
| put_tasklist_impl | instance | (storage, account_name: str, tasklist_key: str, payload: Dict) -> Tuple[Any, int] | Saves a task list. Returns success or an error if the payload is invalid. |
| delete_tasklist_impl | instance | (storage, account_name: str, tasklist_key: str) -> Tuple[Any, int] | Deletes a task list. Returns success or an error if the task list cannot be found. |

## 10. Usage Examples
```python
# Example of creating a chat session
response, status_code = post_chat_impl(chat2_store, agent_manager, {
    "agentName": "example_agent",
    "accountName": "user_account",
    "friendlyName": "User Friendly Name",
    "tags": ["example", "test"]
})

# Example of uploading an image
response, status_code = post_upload_image_impl(config, "user_account", file_data, "image.png", "image/png")
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: Each endpoint implements robust error handling, returning appropriate HTTP status codes and error messages for various failure scenarios.
- **Thread-Safety Concerns**: The module does not explicitly mention thread-safety; care should be taken when accessing shared resources.
- **Known Limitations**: The maximum upload size is configurable but defaults to 10 MB, which may not be sufficient for larger files.
- **Validation Logic**: Each endpoint includes validation for required fields, ensuring that clients receive clear error messages when inputs are missing or invalid.

## 12. Consumers
| Consumer                       | What it uses                                      |
|-------------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm | Various endpoints for managing agents, chats, documents, and metrics. | 

---

This document provides a comprehensive overview of the `src/http_endpoints` module, detailing its structure, functionality, and usage.