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
  - GenerateDocHandler
  - CurateChatHandler
  - GenerateImageHandler
  - GenerateSvgHandler
  - EmbeddingHandler
  - TasklistsManageHandler
  - TasklistsRunHandler
  - LazyToolSelectorHandler
  - ToolSelectionProbeHandler
```

## 1. Summary
The `src/handlers` module provides a collection of handler classes that facilitate various operations within the Lucy project. Each handler is designed to perform a specific task, such as managing files, executing commands, scraping web pages, or handling chat sessions. This modular approach allows for easy integration and extensibility, enabling the system to interact with different components and services seamlessly.

The handlers fit into the overall architecture by acting as intermediaries between user requests and the underlying services or data stores. They encapsulate the logic required to process requests, validate inputs, and return structured responses, thus simplifying the interaction with complex functionalities.

The primary problem this module solves is the need for a flexible and organized way to manage various operations that can be invoked by agents or users, ensuring that each operation adheres to a consistent interface and error handling mechanism.

## 2. Architecture & Design
The `src/handlers` module employs several design patterns and principles:

- **Handler Pattern**: Each handler class implements a consistent interface defined by the `HandlerV2` abstract base class. This ensures that all handlers provide methods for defining their tool specifications and executing their logic.
  
- **Dependency Injection**: Handlers receive configuration and context through their constructors and method parameters, allowing for flexible configuration and easier testing.

- **Error Handling**: Each handler is designed to return structured error messages, making it easier for clients to understand what went wrong during execution.

- **Modularity**: The handlers are organized into separate files, each responsible for a specific functionality. This modularity enhances maintainability and allows for easier updates or replacements of individual handlers.

- **Lazy Loading**: Some handlers are imported conditionally based on the availability of optional dependencies, allowing the system to remain functional even in environments where certain libraries are not installed.

The design decisions evident from comments and docstrings emphasize the importance of clear error reporting, input validation, and adherence to a consistent interface across all handlers.

## 3. Key Classes
| Class                          | Base/Parent         | Purpose                                                                 |
|--------------------------------|---------------------|-------------------------------------------------------------------------|
| FileLoadHandler2               | HandlerV2           | Loads text files and returns their contents.                           |
| FileSaveHandler2               | HandlerV2           | Saves text or code into a specified file.                              |
| CommandExecutionHandler2       | HandlerV2           | Executes system commands in a controlled environment.                  |
| ScrapeWebPageHandler2          | HandlerV2           | Scrapes text from web pages.                                          |
| WebSearchHandler2              | HandlerV2           | Performs web searches using the Brave Search API.                     |
| Chat2Handler                   | HandlerV2           | Manages chat sessions and their events.                                |
| ResetSessionHandler            | HandlerV2           | Resets the current chat session.                                       |
| RemoteExecuteHandler           | HandlerV2           | Queries a remote Lucy instance via its API.                           |
| ToolHandlerMetaHandler         | HandlerV2           | Provides metadata about available tools.                               |
| AgentsManageHandler            | HandlerV2           | Manages agent definitions at runtime.                                  |
| GetKeywordsHandler             | HandlerV2           | Extracts keywords from text.                                           |
| GenerateDocHandler             | HandlerV2           | Generates documentation for Python modules.                            |
| CurateChatHandler              | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving events.  |
| GenerateImageHandler           | HandlerV2           | Generates simple images and returns them as base64 data URIs.         |
| GenerateSvgHandler             | HandlerV2           | Validates and sanitizes SVG markup.                                   |
| EmbeddingHandler               | HandlerV2           | Generates and compares vector embeddings.                              |
| TasklistsManageHandler         | HandlerV2           | Manages tasklists and their tasks.                                     |
| TasklistsRunHandler            | HandlerV2           | Executes persisted tasklists.                                         |
| LazyToolSelectorHandler        | HandlerV2           | Probes the lazy tool-loading mechanism.                                |
| ToolSelectionProbeHandler      | HandlerV2           | Diagnoses the tool selection pipeline.                                  |

## 4. Source Files
| File                              | Responsibility                                           | Notable Exports                                                                 |
|-----------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                     | Package exports for handler implementations.            | Exposes commonly used handler implementations.                                 |
| `agents_manage_handler.py`        | Manages agent definitions at runtime.                   | `AgentsManageHandler`                                                           |
| `chat2_handler.py`                | Manages chat sessions.                                  | `Chat2Handler`                                                                  |
| `command_execution_handler2.py`   | Executes system commands.                               | `CommandExecutionHandler2`                                                      |
| `curate_chat_handler.py`          | Curates chat sessions.                                  | `CurateChatHandler`                                                             |
| `embedding_handler.py`            | Generates and compares embeddings.                      | `EmbeddingHandler`                                                              |
| `file_load_handler2.py`           | Loads text files.                                      | `FileLoadHandler2`                                                              |
| `file_save_handler.py`            | Saves text or code into files.                         | `FileSaveHandler2`                                                              |
| `generate_doc_handler.py`         | Generates documentation for modules.                   | `GenerateDocHandler`                                                            |
| `generate_image_handler.py`       | Generates images and returns them as base64.          | `GenerateImageHandler`                                                           |
| `generate_svg_handler.py`         | Validates and sanitizes SVG markup.                    | `GenerateSvgHandler`                                                             |
| `get_keywords_handler.py`         | Extracts keywords from text.                            | `GetKeywordsHandler`                                                             |
| `handler.py`                      | Abstract base class for handlers.                       | `Handler`                                                                       |
| `handler_registry.py`             | Manages registration of handlers.                       | `HandlerRegistry`                                                                |
| `handler_v2.py`                   | Defines the HandlerV2 interface.                        | `HandlerV2`                                                                     |
| `lazy_tool_selector_handler.py`   | Probes lazy tool loading.                              | `LazyToolSelectorHandler`                                                       |
| `remote_execute_handler.py`       | Queries a remote Lucy instance.                         | `RemoteExecuteHandler`                                                          |
| `reset_session_handler.py`        | Resets chat sessions.                                   | `ResetSessionHandler`                                                           |
| `scrape_web_page_handler2.py`     | Scrapes web pages.                                     | `ScrapeWebPageHandler2`                                                         |
| `serve_image_handler.py`          | Serves images as base64 data URIs.                     | `ServeImageHandler`                                                             |
| `tasklists_manage_handler.py`     | Manages tasklists and tasks.                           | `TasklistsManageHandler`                                                        |
| `tasklists_run_handler.py`        | Executes persisted tasklists.                          | `TasklistsRunHandler`                                                           |
| `tool_handler_meta_handler.py`    | Provides metadata about tools.                          | `ToolHandlerMetaHandler`                                                        |
| `tool_selection_probe_handler.py` | Probes the tool selection pipeline.                     | `ToolSelectionProbeHandler`                                                    |
| `web_search_handler2.py`          | Performs web searches.                                  | `WebSearchHandler2`                                                             |

## 5. Dependencies
### Standard library
- `json`
- `logging`
- `os`
- `shlex`
- `subprocess`
- `sys`
- `re`
- `io`
- `hashlib`
- `xml.etree.ElementTree`

### Third-party packages
- `requests`
- `PIL` (Pillow)
- `pydantic`

### Internal modules
- `src.config_manager`
- `src.handlers.handler_v2`
- `src.storage.json_file_storage`
- `src.storage_paths.storage_paths`
- `src.tasklists.service`
- `src.keywords.keywords`
- `src.tool_selection`
- `src.message_processors.automation_processor`
- `src.message_processors.lazy_tool_selection`

### Optional dependencies
- Handlers that depend on NLP libraries (spaCy, nltk, sklearn) are imported lazily.

## 6. Configuration / Settings
| Key                          | Type   | Default | What it controls                                      |
|------------------------------|--------|---------|------------------------------------------------------|
| `storage_root_path`          | string | None    | Base path for storage operations.                    |
| `storage_namespace`          | string | None    | Namespace for storage operations.                    |
| `tasklists.run_ttl_days`    | int    | 7       | Time-to-live for tasklist runs.                     |
| `credential_path`            | string | None    | Path to credentials for external services.           |
| `chat2_store_backend`        | string | "jsonl" | Backend for chat2 storage (jsonl or sqlite).        |
| `curation_llm_model`        | string | "gpt-4o-mini" | LLM model used for curation tasks.               |
| `external_roots`            | dict   | {}      | Mapping of external root names to paths.             |

## 7. Exceptions
| Exception                     | Base                     | When Raised                                                  |
|-------------------------------|--------------------------|-------------------------------------------------------------|
| `ValueError`                  | Exception                | Raised for invalid arguments or configuration issues.       |
| `FileNotFoundError`           | Exception                | Raised when a specified file cannot be found.              |
| `requests.exceptions.RequestException` | Exception      | Raised for errors during HTTP requests.                     |
| `ValidationError`             | Exception                | Raised when input validation fails in Pydantic models.     |

## 8. Module-Level Constants
| Constant                      | Value                     |
|-------------------------------|---------------------------|
| `DEFAULT_MAX_DIMENSION`       | 512                       |
| `MAX_ALLOWED_DIMENSION`       | 512                       |

## 9. Methods (by class)
### FileLoadHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Loads a file and returns its content.                                      |

### FileSaveHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Saves content to a specified file.                                         |

### CommandExecutionHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Executes a command in a specified location.                               |

### ScrapeWebPageHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Scrapes a web page and returns its content.                               |

### WebSearchHandler2
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Performs a web search and returns results.                                 |

### Chat2Handler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Manages chat sessions and their events.                                    |

### ResetSessionHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Resets the current chat session.                                           |

### RemoteExecuteHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Queries a remote Lucy instance and returns the result.                    |

### ToolHandlerMetaHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Provides metadata about available tools.                                   |

### AgentsManageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:` | Manages agent definitions at runtime.                                      |

### GetKeywordsHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any]:` | Extracts keywords from the provided content.                               |

### GenerateDocHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Generates documentation for a module.                                      |

### CurateChatHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Curates chat sessions by filtering, summarizing, or archiving events.      |

### GenerateImageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Generates images and returns them as base64 data URIs.                    |

### GenerateSvgHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Validates and sanitizes SVG markup.                                        |

### EmbeddingHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Generates and compares vector embeddings.                                   |

### TasklistsManageHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Manages tasklists and their tasks.                                         |

### TasklistsRunHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Executes persisted tasklists.                                             |

### LazyToolSelectorHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Probes the lazy tool-loading mechanism.                                    |

### ToolSelectionProbeHandler
| Method         | Type         | Signature                                   | Description                                                                 |
|----------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `execute`      | instance     | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:` | Diagnoses the tool selection pipeline.                                      |

## 10. Usage Examples
### FileLoadHandler2
```python
from src.handlers import FileLoadHandler2

handler = FileLoadHandler2(config)
result = handler.execute({"location": "storage", "external_root": "", "path": "example.txt"})
print(result)
```

### CommandExecutionHandler2
```python
from src.handlers import CommandExecutionHandler2

handler = CommandExecutionHandler2(config)
result = handler.execute({"location": "sandbox", "command": "ls", "working_directory": "."})
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
- **Error Handling**: Each handler is designed to return structured error messages. Ensure that the client code checks for the `ok` field in the response to handle errors gracefully.
- **Dependency Management**: Some handlers may not be available if their dependencies are not installed. Check the logs for warnings about missing handlers.
- **Input Validation**: Handlers perform input validation and will raise errors if required fields are missing or invalid. Always ensure that the input conforms to the expected schema.
- **File Paths**: When dealing with file paths, ensure that they are relative and do not contain any `..` segments to avoid path traversal vulnerabilities.

## 12. Consumers
| Consumer                       | What it uses                                      |
|-------------------------------|---------------------------------------------------|
| `FunctionCallingProcessor`    | Calls various handlers based on user requests.   |
| `AutomationProcessor`         | Executes tasklists and manages task execution.   |
| `ChatSessionManager`          | Uses chat-related handlers for managing sessions. |
| `WebScraper`                 | Utilizes `ScrapeWebPageHandler2` for scraping.   |
| `DocumentationGenerator`      | Calls `GenerateDocHandler` for module documentation. |

---

This document provides a comprehensive overview of the `src/handlers` module, detailing its structure, functionality, and usage. It serves as a reference for developers working with or extending the module.