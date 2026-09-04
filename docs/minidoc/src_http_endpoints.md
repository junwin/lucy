```markdown
---
tags:
  - http_endpoints
  - lucyproject
  - TaskList
  - ChatEvent
  - AgentManager
  - Chat2Store
  - MetricsRepository
---

## 1. Summary
The `http_endpoints` module provides a set of HTTP endpoint implementations for managing various resources such as agents, chats, task lists, documents, and metrics. It facilitates CRUD operations and interactions with underlying storage systems, enabling users to manage tasks, chat sessions, and document searches effectively.

## 2. Key Classes
| Class         | Base/Parent | Purpose                                      |
|---------------|-------------|----------------------------------------------|
| TaskList      | N/A         | Represents a list of tasks for a user.      |
| ChatEvent     | N/A         | Represents an event in a chat session.       |
| AgentManager  | N/A         | Manages agent instances and their validity.  |
| Chat2Store    | N/A         | Manages chat session storage and retrieval.  |
| MetricsRepository | N/A     | Handles querying and storing metrics data.   |

## 3. Source Files
| File                             | Responsibility                                      | Notable Exports                     |
|----------------------------------|----------------------------------------------------|-------------------------------------|
| agents_endpoints.py              | Manages agent-related endpoints.                    | get_agents_impl                     |
| chats_endpoints.py               | Handles chat session endpoints.                     | post_chat_impl, get_chat_impl       |
| context_endpoints.py             | Manages context-related endpoints.                  | list_context_names_impl             |
| documents_endpoints.py           | Handles document search endpoints.                  | search_documents_impl                |
| metrics_endpoints.py             | Provides metrics querying endpoints.                | get_metrics_runs_impl                |
| prompt_and_docs_endpoints.py     | Manages prompt building and document search.        | build_prompt_impl, search_documents_impl |
| prompt_builder_debug_endpoints.py | Debugging tool for prompt builder effectiveness.    | prompt_builder_debug_impl            |
| prompt_builder_endpoints.py      | Handles prompt building requests.                   | build_prompt_impl                    |
| prompt_builder_metrics_endpoints.py | Provides metrics for prompt building.              | prompt_builder_metrics_impl          |
| tasklist_endpoints.py            | Manages task list CRUD operations.                  | list_tasklists_impl, get_tasklist_impl |
| upload_endpoints.py              | Handles file/image uploads.                         | post_upload_image_impl               |

## 4. Dependencies
- **Standard library**
  - logging
  - os
  - json
  - uuid
  - datetime
  - typing
- **Third-party packages**
  - None
- **Internal modules**
  - src.tasklists
  - src.agent
  - src.chat2.facade
  - src.chat2.models
  - src.metrics
  - src.config_manager
  - src.storage.interfaces
  - src.utils.document_context
  - src.utils.text_snippet_loader
  - src.keywords.keywords
  - src.handlers.handler_registry
  - src.message_processors.function_calling_processor

## 5. Methods (by class)

### TaskList
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| from_dict                  | Class       | `TaskList.from_dict(payload: Dict)`           | Creates a TaskList instance from a dictionary.                            |
| to_dict                    | Instance    | `TaskList.to_dict()`                           | Converts the TaskList instance to a dictionary.                           |

### ChatEvent
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| __init__                   | Instance    | `ChatEvent(role: str, actor: str, kind: str, payload: Any, metadata: Optional[Dict] = None)` | Initializes a ChatEvent instance.                                          |

### AgentManager
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| is_valid                   | Instance    | `AgentManager.is_valid(agent_name: str)`      | Checks if the specified agent name is valid.                              |
| get_agent                  | Instance    | `AgentManager.get_agent(agent_name: str)`     | Retrieves the agent instance by name.                                      |

### Chat2Store
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| create_session             | Instance    | `Chat2Store.create_session(...)`               | Creates a new chat session.                                                |
| list_sessions              | Instance    | `Chat2Store.list_sessions(...)`                | Lists chat sessions based on parameters.                                   |
| get_session                | Instance    | `Chat2Store.get_session(session_id: str)`     | Retrieves a chat session by ID.                                           |
| stream_events              | Instance    | `Chat2Store.stream_events(session_id: str)`    | Streams events for a specific chat session.                               |
| add_event                  | Instance    | `Chat2Store.add_event(session_id: str, event: ChatEvent)` | Adds an event to a chat session.                                          |

### MetricsRepository
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| query                      | Instance    | `MetricsRepository.query(...)`                 | Queries the metrics repository based on provided parameters.              |
```