# Module Documentation for `src/http_endpoints`

## YAML Front Matter
```yaml
tags:
  - src_http_endpoints
  - lucyproject
  - TaskList
  - ChatEvent
  - Chat2Store
  - MetricsRepository
  - PromptBuilder
```

## 1. Summary
The `src/http_endpoints` module provides a set of HTTP endpoint implementations for managing various functionalities related to agents, chats, task lists, documents, and metrics within the Lucy project. It serves as a bridge between client requests and the underlying business logic, facilitating operations such as creating, retrieving, updating, and deleting resources. This module fits into the overall architecture by handling HTTP requests and responses, ensuring that the application can interact with external clients effectively. It solves the problem of managing complex interactions with various data entities in a structured and RESTful manner.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: Many functions utilize dependency injection to obtain instances of services like `Chat2Store`, `AgentManager`, and `MetricsRepository`, promoting loose coupling and easier testing.
- **Error Handling**: Each endpoint implementation includes robust error handling, logging exceptions, and returning appropriate HTTP status codes and error messages.

Classes and functions within the module are designed to adhere to specific protocols, ensuring that they can be easily replaced or extended. The module does not appear to have a legacy/v2 split, indicating a focus on maintaining a single, coherent codebase.

Important design decisions include:
- The use of structured response formats, which standardizes how data is returned to clients.
- The separation of concerns, where each endpoint implementation is responsible for a specific resource type, enhancing maintainability.

## 3. Key Classes
| Class          | Base/Parent | Purpose                                      |
|----------------|-------------|----------------------------------------------|
| TaskList       | None        | Represents a list of tasks for a user.      |
| ChatEvent      | None        | Represents an event in a chat session.       |
| Chat2Store     | None        | Manages chat session storage and retrieval.  |
| MetricsRepository | None     | Handles metrics data storage and querying.   |
| PromptBuilder   | None       | Constructs prompts based on user queries.    |

## 4. Source Files
| File                             | Responsibility                                      | Notable Exports                     |
|----------------------------------|----------------------------------------------------|-------------------------------------|
| agents_endpoints.py              | Manages agent-related HTTP endpoints.               | get_agents_impl, list_context_names_impl |
| chats_endpoints.py               | Handles chat session-related HTTP endpoints.        | post_chat_impl, get_chats_impl     |
| context_endpoints.py             | Manages context-related HTTP endpoints.             | list_context_names_impl             |
| documents_endpoints.py           | Handles document search-related HTTP endpoints.     | search_documents_impl                |
| metrics_endpoints.py             | Manages metrics-related HTTP endpoints.             | get_metrics_runs_impl               |
| prompt_and_docs_endpoints.py     | Handles prompt building and document search.        | build_prompt_impl, search_documents_impl |
| prompt_builder_debug_endpoints.py | Provides debugging for prompt builder.              | prompt_builder_debug_impl            |
| prompt_builder_endpoints.py      | Manages prompt building HTTP endpoints.             | build_prompt_impl                   |
| prompt_builder_metrics_endpoints.py | Provides metrics for prompt building.              | prompt_builder_metrics_impl          |
| tasklist_endpoints.py            | Manages task list-related HTTP endpoints.           | list_tasklists_impl, get_tasklist_impl |
| upload_endpoints.py              | Handles file/image upload HTTP endpoints.           | post_upload_image_impl              |

## 5. Dependencies
- **Standard library**:
  - `logging`
  - `json`
  - `os`
  - `uuid`
  - `datetime`
  - `typing`
  
- **Third-party packages**: None identified.

- **Internal modules**:
  - `src.tasklists`
  - `src.agent`
  - `src.chat2.facade`
  - `src.metrics`
  - `src.prompt_builders.prompt_builder`
  - `src.storage.interfaces`
  - `src.config_manager`
  - `src.utils.document_context`
  - `src.utils.text_snippet_loader`
  - `src.keywords.keywords`
  
- **Optional dependencies**: None identified.

## 6. Configuration / Settings
| Key                          | Type   | Default                       | What it controls                          |
|------------------------------|--------|-------------------------------|-------------------------------------------|
| storage_root_path            | str    | /home/junwin/lucy_storage    | Base path for storage files.             |
| storage_namespace             | str    | data                          | Namespace for storage organization.       |
| max_upload_size_bytes        | int    | 10485760 (10 MB)             | Maximum allowed upload size for files.   |
| metrics_runs_log_path        | str    | metrics/runs.jsonl           | Path for metrics runs log.               |

## 7. Exceptions
| Exception                    | Base         | When Raised                                      |
|------------------------------|--------------|-------------------------------------------------|
| None                         | None         | No custom exceptions defined in this module.    |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| ALLOWED_IMAGE_MIME_TYPES     | {"image/png", "image/jpeg", ...} |
| EXT_BY_MIME                  | {"image/png": ".png", ...}    |

## 9. Methods (by class)
### TaskList
| Method                      | Type        | Signature                                   | Description |
|-----------------------------|-------------|---------------------------------------------|-------------|
| from_dict                   | class       | `@classmethod from_dict(cls, data: dict)` | Creates a TaskList instance from a dictionary. |
| to_dict                     | instance    | `def to_dict(self) -> dict`                | Converts the TaskList instance to a dictionary. |

### ChatEvent
| Method                      | Type        | Signature                                   | Description |
|-----------------------------|-------------|---------------------------------------------|-------------|
| __init__                    | instance    | `def __init__(self, role: str, ...)`      | Initializes a ChatEvent instance. |

### Chat2Store
| Method                      | Type        | Signature                                   | Description |
|-----------------------------|-------------|---------------------------------------------|-------------|
| create_session              | instance    | `def create_session(...)`                   | Creates a new chat session. |
| list_sessions               | instance    | `def list_sessions(...)`                    | Lists all chat sessions. |
| get_session                 | instance    | `def get_session(...)`                      | Retrieves a specific chat session. |

### MetricsRepository
| Method                      | Type        | Signature                                   | Description |
|-----------------------------|-------------|---------------------------------------------|-------------|
| query                       | instance    | `def query(...)`                            | Queries the metrics repository. |

### PromptBuilder
| Method                      | Type        | Signature                                   | Description |
|-----------------------------|-------------|---------------------------------------------|-------------|
| build_prompt                | instance    | `def build_prompt(...)`                     | Constructs a prompt based on input parameters. |

## 10. Usage Examples
```python
# Example of creating a chat session
response, status = post_chat_impl(chat2_store, agent_manager, {
    "agentName": "example_agent",
    "accountName": "user_account",
    "friendlyName": "User Friendly Name",
    "tags": ["tag1", "tag2"]
})

# Example of uploading an image
response, status = post_upload_image_impl(config, "user_account", file_data, "image.png", "image/png")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: Each endpoint has robust error handling, returning appropriate HTTP status codes and messages for various error conditions.
- **Validation**: Many endpoints validate input parameters and return errors for missing or invalid data.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when accessing shared resources.
- **File Upload Limits**: The maximum file upload size is configurable, and exceeding this limit will result in a 413 error.

## 12. Consumers
| Consumer                     | What it uses                                   |
|------------------------------|------------------------------------------------|
| src.http_endpoints.agents_endpoints | get_agents_impl, list_context_names_impl |
| src.http_endpoints.chats_endpoints  | post_chat_impl, get_chats_impl          |
| src.http_endpoints.documents_endpoints | search_documents_impl                   |
| src.http_endpoints.metrics_endpoints  | get_metrics_runs_impl                   |
| src.http_endpoints.tasklist_endpoints | list_tasklists_impl, get_tasklist_impl  |
| src.http_endpoints.upload_endpoints    | post_upload_image_impl                  |

This documentation provides a comprehensive overview of the `src/http_endpoints` module, detailing its structure, functionality, and usage.