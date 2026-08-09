```markdown
---
tags:
  - http_endpoints
  - lucyproject
  - AgentManager
  - Chat2Store
  - ChatEvent
  - PromptBuilder
  - Storage
  - ConfigManager
---

## 1. Summary
The `http_endpoints` module provides a set of HTTP endpoint implementations for managing various aspects of a chat and task management system. It serves as an interface for clients to interact with backend services, allowing operations such as creating chat sessions, managing task lists, uploading files, and searching documents. This module fits into the overall architecture as a crucial layer that facilitates communication between the client-side applications and the underlying data storage and processing services. It effectively solves the problem of exposing complex backend functionalities through simple HTTP requests, enabling easy integration and interaction.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: The use of `PromptBuilder` and other services is managed through dependency injection, allowing for better modularity and testability.
- **Error Handling**: Each endpoint implementation includes robust error handling, logging exceptions, and returning appropriate HTTP status codes and error messages.

Classes within the module are primarily composed of functions that handle specific HTTP requests. There is no inheritance among classes, but there is a clear separation of concerns, with each file focusing on a specific aspect of the system (e.g., agents, chats, task lists). The module does not appear to have a legacy/v2 split, indicating a unified approach to its design.

Important design decisions include:
- The use of structured logging to capture errors and important events, which aids in debugging and monitoring.
- The decision to return detailed error messages to the client, enhancing the user experience by providing clear feedback.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| AgentManager  | None        | Manages agent-related operations and validations. |
| Chat2Store    | None        | Handles storage operations for chat sessions.     |
| ChatEvent     | None        | Represents events in a chat session.              |
| PromptBuilder  | None        | Constructs prompts based on user queries.         |
| Storage       | None        | Abstract base for storage operations.             |
| ConfigManager | None        | Manages configuration settings for the application.|

## 4. Source Files
| File                             | Responsibility                                      | Notable Exports                     |
|----------------------------------|----------------------------------------------------|-------------------------------------|
| agents_endpoints.py              | Handles agent-related HTTP requests.               | get_agents_impl                     |
| chats_endpoints.py               | Manages chat session operations.                   | post_chat_impl, get_chats_impl      |
| context_endpoints.py             | Provides context management functionalities.        | list_context_names_impl             |
| documents_endpoints.py           | Implements document search functionalities.        | search_documents_impl                |
| prompt_and_docs_endpoints.py     | Manages prompt building and document searching.    | build_prompt_impl, search_documents_impl |
| prompt_builder_debug_endpoints.py | Debugging tools for prompt builder effectiveness.  | prompt_builder_debug_impl            |
| prompt_builder_endpoints.py      | Handles prompt building requests.                  | build_prompt_impl                    |
| tasklist_endpoints.py            | Manages task list operations.                      | list_tasklists_impl, get_tasklist_impl |
| upload_endpoints.py              | Handles file uploads.                              | post_upload_image_impl               |

## 5. Dependencies
- **Standard library**:
  - `logging`
  - `json`
  - `os`
  - `uuid`
  - `datetime`
  - `typing`
  
- **Third-party packages**: None

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

- **Optional dependencies**: None

## 6. Configuration / Settings
| Key                     | Type   | Default                     | What it controls                          |
|-------------------------|--------|-----------------------------|-------------------------------------------|
| storage_root_path       | str    | /home/junwin/lucy_storage  | Root path for storage operations.         |
| storage_namespace        | str    | data                        | Namespace for organizing storage.         |
| max_upload_size_bytes    | int    | 10 * 1024 * 1024           | Maximum allowed upload size in bytes.    |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      |      | None        |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| ALLOWED_IMAGE_MIME_TYPES     | { "image/png", "image/jpeg", "image/gif", "image/webp" } |
| EXT_BY_MIME                  | { "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp" } |

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

### ConfigManager
| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| N/A    |      |           | N/A         |

### HTTP Endpoint Implementations
#### agents_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| get_agents_impl            | function     | get_agents_impl(agent_manager)    | Retrieves available agents. Returns a list of agents and HTTP status. |
#### chats_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| post_chat_impl             | function     | post_chat_impl(chat2_store, agent_manager, payload) | Creates a new chat session. Returns session details and HTTP status. |
| get_chats_impl             | function     | get_chats_impl(chat2_store, agent_manager, agent_name, account_name, limit) | Retrieves chat sessions based on filters. Returns a list of sessions and HTTP status. |
| get_chat_impl              | function     | get_chat_impl(chat2_store, session_id) | Retrieves a specific chat session by ID. Returns session details and HTTP status. |
| post_chat_message_impl      | function     | post_chat_message_impl(chat2_store, session_id, data) | Adds a message to a chat session. Returns status and HTTP status. |
| delete_chat_impl           | function     | delete_chat_impl(chat2_store, session_id) | Deletes a chat session by ID. Returns status and HTTP status. |
| update_chat_impl           | function     | update_chat_impl(chat2_store, session_id, payload) | Updates a chat session's metadata. Returns status and HTTP status. |
#### context_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| list_context_names_impl    | function     | list_context_names_impl(storage, account_name) | Lists context names for a given account. Returns a list and HTTP status. |
#### documents_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| search_documents_impl      | function     | search_documents_impl(storage, data) | Searches for documents based on query parameters. Returns search results and HTTP status. |
#### prompt_and_docs_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| build_prompt_impl          | function     | build_prompt_impl(agent_manager, storage, container, config, payload) | Builds a prompt based on user input. Returns the prompt and HTTP status. |
| search_documents_impl      | function     | search_documents_impl(storage, data) | Searches for documents based on query parameters. Returns search results and HTTP status. |
#### prompt_builder_debug_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| prompt_builder_debug_impl   | function     | prompt_builder_debug_impl(storage, config, payload) | Analyzes document loading effectiveness without modifying state. Returns a detailed trace and HTTP status. |
#### prompt_builder_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| build_prompt_impl          | function     | build_prompt_impl(agent_manager, storage, container, config, payload) | Builds a prompt based on user input. Returns the prompt and HTTP status. |
#### tasklist_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| list_tasklists_impl        | function     | list_tasklists_impl(storage, account_name) | Lists task lists for a given account. Returns a list and HTTP status. |
| get_tasklist_impl          | function     | get_tasklist_impl(storage, account_name, tasklist_key) | Retrieves a specific task list by key. Returns task list details and HTTP status. |
| put_tasklist_impl          | function     | put_tasklist_impl(storage, account_name, tasklist_key, payload) | Saves a task list. Returns status and HTTP status. |
| delete_tasklist_impl       | function     | delete_tasklist_impl(storage, account_name, tasklist_key) | Deletes a task list by key. Returns status and HTTP status. |
#### upload_endpoints.py
| Method                     | Type         | Signature                          | Description |
|----------------------------|--------------|------------------------------------|-------------|
| post_upload_image_impl      | function     | post_upload_image_impl(config, account_name, file_data, original_filename, mime_type) | Saves an uploaded image and returns its ID and metadata. Returns status and HTTP status. |

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
with open("example_image.png", "rb") as file:
    file_data = file.read()
response, status = post_upload_image_impl(config, "user_account", file_data, "example_image.png", "image/png")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: Each endpoint has robust error handling, returning appropriate HTTP status codes and messages. However, clients should be aware of potential 500 errors due to unhandled exceptions in the backend.
- **Validation**: Many endpoints require specific fields to be present in the payload. Missing fields will result in 400 errors.
- **File Uploads**: The maximum file size for uploads is configurable, and exceeding this limit will result in a 413 error.
- **Thread Safety**: The module does not explicitly mention thread safety, so concurrent requests may lead to race conditions if not handled properly in the underlying storage.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Frontend Application          | Interacts with all endpoints for chat and task management. |
| Other Microservices           | May call specific endpoints for chat or task functionalities. |
```