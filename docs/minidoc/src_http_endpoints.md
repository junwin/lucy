# Module Documentation for `src/http_endpoints`

## YAML Front Matter
```yaml
tags:
  - src_http_endpoints
  - lucyproject
  - AgentManager
  - Chat2Store
  - ChatEvent
  - PromptBuilder
  - Storage
```

## 1. Summary
The `http_endpoints` module provides a set of HTTP endpoint implementations for managing various resources in a chat and task management system. It serves as the interface between client requests and the underlying storage and business logic, facilitating operations such as creating, retrieving, updating, and deleting chat sessions, task lists, and documents. This module fits into the overall architecture as a critical component that handles HTTP requests and responses, ensuring that the application can interact with users and other services effectively. It solves the problem of exposing a RESTful API for managing chat sessions and task lists, allowing for seamless integration with front-end applications and other services.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: The use of `AgentManager`, `Chat2Store`, and `PromptBuilder` indicates a design that favors dependency injection, allowing for easier testing and flexibility.
- **Error Handling**: Each endpoint implementation includes robust error handling, logging exceptions, and returning appropriate HTTP status codes and error messages.

Classes within the module are primarily composed rather than inheriting from a common base class, which promotes loose coupling. The endpoints are designed to be stateless, relying on external storage and services to manage state.

There is no evident legacy or v2 split in the code, but the comments indicate a transition to a new storage system (`Chat2Store`), suggesting a focus on modernizing the architecture.

## 3. Key Classes
| Class        | Base/Parent | Purpose                                           |
|--------------|-------------|---------------------------------------------------|
| AgentManager | None        | Manages agents for chat sessions.                 |
| Chat2Store   | None        | Handles storage operations for chat sessions.     |
| ChatEvent    | None        | Represents events in a chat session.              |
| PromptBuilder| None        | Constructs prompts for chat interactions.         |
| Storage      | None        | Base class for storage operations.                |

## 4. Source Files
| File                             | Responsibility                                      | Notable Exports                     |
|----------------------------------|----------------------------------------------------|-------------------------------------|
| agents_endpoints.py              | Manages agent-related HTTP endpoints.              | get_agents_impl                     |
| chats_endpoints.py               | Manages chat session-related HTTP endpoints.       | post_chat_impl, get_chats_impl      |
| context_endpoints.py             | Manages context-related HTTP endpoints.            | list_context_names_impl             |
| documents_endpoints.py           | Manages document search-related HTTP endpoints.    | search_documents_impl                |
| prompt_and_docs_endpoints.py     | Manages prompt building and document search.       | build_prompt_impl, search_documents_impl |
| prompt_builder_debug_endpoints.py | Provides debugging for prompt builder.             | prompt_builder_debug_impl            |
| prompt_builder_endpoints.py      | Manages prompt building HTTP endpoints.            | build_prompt_impl                    |
| tasklist_endpoints.py            | Manages task list-related HTTP endpoints.          | list_tasklists_impl, get_tasklist_impl |
| upload_endpoints.py              | Manages file upload HTTP endpoints.                | post_upload_image_impl               |
| __init__.py                      | Initializes the module and exports key functions.  | None                                |

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
  - `src.prompt_builders.prompt_builder`
  - `src.config_manager`
  - `src.storage.base`
  - `src.utils.document_context`
  - `src.utils.text_snippet_loader`
  - `src.keywords.keywords`

- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                     | Type   | Default                       | What it controls                          |
|-------------------------|--------|-------------------------------|-------------------------------------------|
| storage_root_path       | str    | /home/junwin/lucy_storage     | Root path for storage files.              |
| storage_namespace        | str    | data                          | Namespace for storage organization.        |
| max_upload_size_bytes    | int    | 10485760 (10 MB)             | Maximum allowed upload size for files.    |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      |      | None        |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| ALLOWED_IMAGE_MIME_TYPES     | {"image/png", "image/jpeg", "image/gif", "image/webp"} |
| EXT_BY_MIME                  | {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"} |

## 9. Methods (by class)
### AgentManager
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### Chat2Store
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### ChatEvent
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### PromptBuilder
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### Storage
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### HTTP Endpoint Methods
#### agents_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| get_agents_impl       | function   | get_agents_impl(agent_manager)    | Retrieves available agents. Returns a list of agents and HTTP status. |
  
#### chats_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| post_chat_impl        | function   | post_chat_impl(chat2_store, agent_manager, payload) | Creates a new chat session. Returns session details and HTTP status. |
| get_chats_impl        | function   | get_chats_impl(chat2_store, agent_manager, agent_name, account_name, limit) | Retrieves chat sessions. Returns a list of sessions and HTTP status. |
| get_chat_impl         | function   | get_chat_impl(chat2_store, session_id) | Retrieves a specific chat session. Returns session details and HTTP status. |
| post_chat_message_impl | function   | post_chat_message_impl(chat2_store, session_id, data) | Adds a message to a chat session. Returns status and HTTP status. |
| delete_chat_impl      | function   | delete_chat_impl(chat2_store, session_id) | Deletes a chat session. Returns status and HTTP status. |
| update_chat_impl      | function   | update_chat_impl(chat2_store, session_id, payload) | Updates a chat session. Returns status and HTTP status. |

#### context_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| list_context_names_impl| function   | list_context_names_impl(storage, account_name) | Lists context names for an account. Returns a list and HTTP status. |

#### documents_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| search_documents_impl  | function   | search_documents_impl(storage, data) | Searches for documents based on a query. Returns search results and HTTP status. |

#### prompt_and_docs_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| build_prompt_impl      | function   | build_prompt_impl(agent_manager, storage, container, config, payload) | Builds a prompt for a chat interaction. Returns the prompt and HTTP status. |
| search_documents_impl   | function   | search_documents_impl(storage, data) | Searches for documents based on a query. Returns search results and HTTP status. |

#### prompt_builder_debug_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| prompt_builder_debug_impl| function   | prompt_builder_debug_impl(storage, config, payload) | Analyzes document loading for a query. Returns a detailed trace and HTTP status. |

#### prompt_builder_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| build_prompt_impl      | function   | build_prompt_impl(agent_manager, storage, container, config, payload) | Builds a prompt for a chat interaction. Returns the prompt and HTTP status. |

#### tasklist_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| list_tasklists_impl    | function   | list_tasklists_impl(storage, account_name) | Lists task lists for an account. Returns a list and HTTP status. |
| get_tasklist_impl      | function   | get_tasklist_impl(storage, account_name, tasklist_name) | Retrieves a specific task list. Returns task list details and HTTP status. |
| put_tasklist_impl      | function   | put_tasklist_impl(storage, account_name, tasklist_name, payload) | Saves a task list. Returns status and HTTP status. |
| delete_tasklist_impl   | function   | delete_tasklist_impl(storage, account_name, tasklist_name) | Deletes a task list. Returns status and HTTP status. |

#### upload_endpoints.py
| Method                | Type       | Signature                          | Description |
|-----------------------|------------|------------------------------------|-------------|
| post_upload_image_impl | function   | post_upload_image_impl(config, account_name, file_data, original_filename, mime_type) | Saves an uploaded image. Returns image ID and metadata. |

## 10. Usage Examples
```python
# Example of creating a chat session
payload = {
    "agentName": "example_agent",
    "accountName": "user_account",
    "friendlyName": "User Friendly Name",
    "tags": ["example", "test"]
}
response, status = post_chat_impl(chat2_store, agent_manager, payload)

# Example of uploading an image
with open("example.png", "rb") as file:
    file_data = file.read()
response, status = post_upload_image_impl(config, "user_account", file_data, "example.png", "image/png")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: Each endpoint has robust error handling, returning appropriate HTTP status codes and messages for various error conditions.
- **Validation**: Many methods validate input parameters and return errors for missing or invalid data.
- **Thread Safety**: The module does not appear to have explicit thread-safety mechanisms, which may be a concern in a multi-threaded environment.
- **Storage Compatibility**: Some methods check for the existence of specific storage capabilities, which may lead to `501 Not Implemented` errors if the storage backend does not support certain operations.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Frontend Application          | Interacts with all HTTP endpoints for chat and task management. |
| Other Microservices           | May call specific endpoints for chat and task operations. |
| Unknown — trace imports to confirm |                                                  |