# Documentation for `src/handlers` Module

## YAML Front Matter
```yaml
tags:
  - src_handlers
  - lucyproject
  - FileLoadHandler2
  - FileSaveHandler2
  - CommandExecutionHandler2
  - ScrapeWebPageHandler2
  - WebSearchHandler2
  - Chat2Handler
  - ResetSessionHandler
  - RemoteExecuteHandler
  - ToolHandlerMetaHandler
  - AgentsManageHandler
  - GetKeywordsHandler
  - CurateChatHandler
  - GenerateDocHandler
  - GenerateImageHandler
  - GenerateSvgHandler
  - EmbeddingHandler
  - TasklistsManageHandler
  - TasklistsRunHandler
  - LazyToolSelectorHandler
  - ToolSelectionProbeHandler
```

## 1. Summary
The `src/handlers` module provides a collection of handler classes that facilitate various operations within the Lucy project. Each handler is designed to perform a specific task, such as managing files, executing commands, scraping web pages, or handling chat sessions. This modular design allows for easy integration and extensibility, enabling the system to interact with different components and services seamlessly.

The handlers fit into the overall architecture as part of the Function Calling Processor (FCP), which orchestrates the execution of tasks based on user requests. By encapsulating functionality within these handlers, the system can maintain a clean separation of concerns, making it easier to manage and extend.

The module addresses the need for a flexible and extensible way to handle various operations, allowing users to interact with the system through a consistent interface.

## 2. Architecture & Design
The design of the `src/handlers` module follows several key principles:

- **Handler Interface**: Each handler implements the `HandlerV2` interface, ensuring a consistent method signature and behavior across all handlers. This interface includes methods for defining tool metadata, executing tasks, and returning results.

- **Dependency Injection**: Handlers receive configuration and context through their constructors and method parameters, promoting loose coupling and easier testing.

- **Error Handling**: Each handler is designed to handle errors gracefully, returning structured error messages that can be easily interpreted by the calling context.

- **Modularity**: The handlers are modular, allowing for easy addition or removal of functionality without affecting the overall system. This is particularly useful for optional features that depend on external libraries.

- **Lazy Loading**: Some handlers are imported lazily to avoid unnecessary dependencies, ensuring that the system can function even in environments where certain libraries are not available.

## 3. Key Classes
| Class                          | Base/Parent         | Purpose                                                                 |
|--------------------------------|---------------------|-------------------------------------------------------------------------|
| FileLoadHandler2               | HandlerV2           | Loads text files and returns their contents.                           |
| FileSaveHandler2               | HandlerV2           | Saves text or code into a specified file.                              |
| CommandExecutionHandler2       | HandlerV2           | Executes system commands in a controlled environment.                  |
| ScrapeWebPageHandler2         | HandlerV2           | Scrapes text from web pages.                                           |
| WebSearchHandler2              | HandlerV2           | Performs web searches using the Brave Search API.                      |
| Chat2Handler                   | HandlerV2           | Manages chat sessions and their events.                                 |
| ResetSessionHandler            | HandlerV2           | Resets the current chat session.                                       |
| RemoteExecuteHandler           | HandlerV2           | Sends queries to a remote Lucy instance.                               |
| ToolHandlerMetaHandler         | HandlerV2           | Provides metadata for registered handlers.                             |
| AgentsManageHandler            | HandlerV2           | Manages agent definitions at runtime.                                  |
| GetKeywordsHandler             | HandlerV2           | Extracts keywords from text.                                           |
| CurateChatHandler              | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving events.  |
| GenerateDocHandler             | HandlerV2           | Generates documentation for Python modules.                            |
| GenerateImageHandler           | HandlerV2           | Generates simple images and returns them as base64 data URIs.         |
| GenerateSvgHandler             | HandlerV2           | Validates and sanitizes SVG markup.                                    |
| EmbeddingHandler               | HandlerV2           | Generates and compares vector embeddings.                               |
| TasklistsManageHandler         | HandlerV2           | Manages tasklists and tasks.                                           |
| TasklistsRunHandler            | HandlerV2           | Executes persisted tasklists.                                          |
| LazyToolSelectorHandler        | HandlerV2           | Probes the lazy tool-loading mechanism.                                 |
| ToolSelectionProbeHandler      | HandlerV2           | Diagnoses the tool selection pipeline.                                  |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                                                                 |
|----------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                    | Package exports for handler implementations.            | Exposes all handler classes for easy import.                                   |
| `agents_manage_handler.py`       | Manages agent definitions at runtime.                   | `AgentsManageHandler`                                                           |
| `chat2_handler.py`               | Manages chat2 session management.                       | `Chat2Handler`                                                                  |
| `command_execution_handler2.py`  | Executes system commands.                               | `CommandExecutionHandler2`                                                      |
| `curate_chat_handler.py`         | Curates chat sessions.                                  | `CurateChatHandler`                                                             |
| `embedding_handler.py`           | Generates and compares embeddings.                      | `EmbeddingHandler`                                                              |
| `file_load_handler2.py`          | Loads text files.                                      | `FileLoadHandler2`                                                              |
| `file_save_handler.py`           | Saves text or code into files.                         | `FileSaveHandler2`                                                              |
| `generate_doc_handler.py`        | Generates documentation for Python modules.            | `GenerateDocHandler`                                                            |
| `generate_image_handler.py`      | Generates simple images.                                | `GenerateImageHandler`                                                          |
| `generate_svg_handler.py`        | Validates and sanitizes SVG markup.                    | `GenerateSvgHandler`                                                            |
| `lazy_tool_selector_handler.py`  | Probes lazy tool loading.                              | `LazyToolSelectorHandler`                                                       |
| `remote_execute_handler.py`      | Queries a remote Lucy instance.                        | `RemoteExecuteHandler`                                                          |
| `reset_session_handler.py`       | Resets the current chat session.                       | `ResetSessionHandler`                                                           |
| `scrape_web_page_handler2.py`    | Scrapes web pages.                                    | `ScrapeWebPageHandler2`                                                         |
| `tasklists_manage_handler.py`    | Manages tasklists and tasks.                          | `TasklistsManageHandler`                                                        |
| `tasklists_run_handler.py`       | Executes persisted tasklists.                          | `TasklistsRunHandler`                                                           |
| `tool_handler_meta_handler.py`   | Returns tool metadata for registered handlers.        | `ToolHandlerMetaHandler`                                                        |
| `web_search_handler2.py`         | Performs web searches.                                 | `WebSearchHandler2`                                                              |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `shlex`
  - `subprocess`
  - `sys`
  - `re`
  - `io`
  
- **Third-party packages**:
  - `requests`
  - `PIL` (Pillow)
  - `pydantic`
  
- **Internal modules**:
  - `src.config_manager`
  - `src.handlers.handler_v2`
  - `src.storage.interfaces`
  - `src.storage.json_file_storage`
  - `src.storage_paths.storage_paths`
  - `src.tasklists.service`
  - `src.tasklists.task`
  - `src.tasklists.task_list`
  - `src.tasklists.task_states`
  - `src.keywords.keywords`
  - `src.tool_selection`
  
- **Optional dependencies**:
  - Handlers that depend on NLP libraries (e.g., `spaCy`, `nltk`, `sklearn`) are imported lazily.

## 6. Configuration / Settings
| Key                          | Type   | Default                       | What it controls                                      |
|------------------------------|--------|-------------------------------|------------------------------------------------------|
| `storage_root_path`          | string | N/A                           | Base path for storage operations.                     |
| `storage_namespace`           | string | N/A                           | Namespace for storage operations.                     |
| `credential_path`            | string | N/A                           | Path to credentials for external services.           |
| `chat2_store_backend`        | string | N/A                           | Backend for chat2 storage (e.g., SQLite, JSON).     |
| `curation_llm_model`         | string | `gpt-4o-mini`                | LLM model used for curation tasks.                   |
| `code_sandbox_path`          | string | N/A                           | Path for sandbox execution.                           |
| `external_roots`             | dict   | N/A                           | Mapping of external root keys to paths.              |

## 7. Exceptions
| Exception                     | Base                     | When Raised                                                                 |
|-------------------------------|--------------------------|-----------------------------------------------------------------------------|
| `FileNotFoundError`           | `OSError`                | Raised when a file cannot be found during load operations.                 |
| `ValueError`                  | `Exception`              | Raised for invalid arguments or when paths are outside allowed directories. |
| `KeyError`                    | `Exception`              | Raised when attempting to access a non-existent key in a dictionary.       |
| `ValidationError`             | `Exception`              | Raised when input validation fails in Pydantic models.                     |

## 8. Module-Level Constants
| Constant                      | Value                     | Description                                           |
|-------------------------------|---------------------------|-------------------------------------------------------|
| `DEFAULT_MAX_DIMENSION`       | 512                       | Default maximum dimension for images.                 |
| `MAX_ALLOWED_DIMENSION`       | 512                       | Hard cap for maximum dimension to prevent oversized images. |

## 9. Methods (by class)
### FileLoadHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Loads a file and returns its contents.                                     |

### FileSaveHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Saves content to a specified file.                                         |

### CommandExecutionHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Executes a command in a specified location.                                |

### ScrapeWebPageHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Scrapes a web page and returns its text content.                           |

### WebSearchHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Performs a web search and returns results.                                 |

### Chat2Handler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Manages chat sessions and their events.                                     |

### ResetSessionHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Resets the current chat session.                                           |

### RemoteExecuteHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Sends a query to a remote Lucy instance.                                   |

### ToolHandlerMetaHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Returns metadata for registered handlers.                                   |

### AgentsManageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Manages agent definitions at runtime.                                      |

### GetKeywordsHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any]:` | Extracts keywords from text.                                               |

### CurateChatHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Curates chat sessions by filtering, summarizing, or archiving events.      |

### GenerateDocHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Generates documentation for Python modules.                                |

### GenerateImageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Generates simple images and returns them as base64 data URIs.             |

### GenerateSvgHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Validates and sanitizes SVG markup.                                       |

### EmbeddingHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Generates and compares vector embeddings.                                   |

### TasklistsManageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Manages tasklists and tasks.                                               |

### TasklistsRunHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:` | Executes persisted tasklists.                                             |

### LazyToolSelectorHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Probes the lazy tool-loading mechanism.                                     |

### ToolSelectionProbeHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Diagnoses the tool selection pipeline.                                      |

## 10. Usage Examples
### FileLoadHandler2
```python
from src.handlers import FileLoadHandler2

handler = FileLoadHandler2(config)
result = handler.execute({"path": "example.txt", "location": "storage", "external_root": ""})
print(result)
```

### CommandExecutionHandler2
```python
from src.handlers import CommandExecutionHandler2

handler = CommandExecutionHandler2(config)
result = handler.execute({"command": "ls", "location": "sandbox", "working_directory": "."})
print(result)
```

### WebSearchHandler2
```python
from src.handlers import WebSearchHandler2

handler = WebSearchHandler2(config)
result = handler.execute({"query": "OpenAI", "count": 5})
print(result)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: Each handler has its own error handling mechanism. Ensure that the calling context is prepared to handle structured error responses.
- **Dependency Management**: Some handlers may not be available if their dependencies are not installed. Check for warnings in the logs if a handler fails to register.
- **Path Validation**: Handlers that deal with file paths enforce strict validation to prevent directory traversal attacks. Ensure that paths are always relative and do not contain `..` segments.
- **Resource Limits**: Be aware of limits on input sizes, especially for SVG and image generation, to avoid exceeding tool-result limits.

## 12. Consumers
| Consumer                       | What it uses                                      |
|-------------------------------|---------------------------------------------------|
| FunctionCallingProcessor       | Calls various handlers based on user requests.   |
| TasklistService               | Uses TasklistsManageHandler for task management.  |
| AutomationProcessor            | Uses TasklistsRunHandler for executing tasklists. |
| Chat2Store                    | Interacts with Chat2Handler for session management. |
| External APIs                 | Utilizes WebSearchHandler2 for web searches.     |

---

This document provides a comprehensive overview of the `src/handlers` module, detailing its structure, functionality, and usage. It serves as a reference for developers working with the Lucy project, ensuring they understand how to effectively utilize the various handlers available.