# Documentation for `src/handlers` Module

## YAML Front Matter
```yaml
tags:
  - src_handlers
  - lucyproject
  - Chat2Handler
  - CommandExecutionHandler2
  - CurateChatHandler
  - DelegateTasksHandler
  - EmbeddingHandler
  - FileLoadHandler2
  - FileSaveHandler2
  - GenerateDocHandler
  - GenerateImageHandler
  - GenerateSvgHandler
  - GetKeywordsHandler
  - ResetSessionHandler
  - ScrapeWebPageHandler2
  - TasklistsManageHandler
  - TasklistsRunHandler
  - WebSearchHandler2
```

## 1. Summary
The `src/handlers` module provides a collection of handler classes that facilitate various operations within the Lucy project. Each handler implements the `HandlerV2` interface, allowing for structured interactions with external services, file operations, and task management. The module is designed to support a wide range of functionalities, including web scraping, file handling, task delegation, and keyword extraction, thereby enabling the core functionalities of the Lucy project.

This module fits into the overall architecture as a key component that manages interactions between the application and external resources or services. It solves the problem of providing a consistent interface for various operations, allowing for easy integration and extensibility.

## 2. Architecture & Design
The design of the `src/handlers` module follows the **Handler** pattern, where each handler is responsible for a specific type of operation. The handlers inherit from the abstract base class `HandlerV2`, which enforces a consistent interface across all handlers. 

Key design patterns used include:
- **Strategy Pattern**: Each handler encapsulates a specific strategy for performing its designated task.
- **Factory Pattern**: The `HandlerRegistry` class acts as a factory for creating handler instances based on their names.

The handlers are designed to be modular and reusable, allowing for easy addition of new functionalities. The use of Pydantic models for input validation ensures that the handlers receive well-structured data.

There is no explicit legacy/v2 split in this module, as all handlers conform to the `HandlerV2` interface. Important design decisions include the use of lazy imports for handlers that depend on optional libraries, ensuring that the module can be loaded in environments where those libraries are not available.

## 3. Key Classes
| Class                          | Base/Parent         | Purpose                                                                 |
|--------------------------------|---------------------|-------------------------------------------------------------------------|
| Chat2Handler                   | HandlerV2           | Manages chat session operations.                                        |
| CommandExecutionHandler2       | HandlerV2           | Executes shell commands in a controlled environment.                   |
| CurateChatHandler              | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving events.  |
| DelegateTasksHandler           | HandlerV2           | Manages task delegation for goals.                                     |
| EmbeddingHandler               | HandlerV2           | Generates and compares vector embeddings.                               |
| FileLoadHandler2               | HandlerV2           | Loads text files from specified locations.                             |
| FileSaveHandler2               | HandlerV2           | Saves text files to specified locations.                               |
| GenerateDocHandler             | HandlerV2           | Generates documentation for Python modules.                            |
| GenerateImageHandler           | HandlerV2           | Generates simple images and returns them as base64 data URIs.         |
| GenerateSvgHandler             | HandlerV2           | Validates and sanitizes SVG markup.                                    |
| GetKeywordsHandler             | HandlerV2           | Extracts keywords from text.                                           |
| ResetSessionHandler            | HandlerV2           | Resets the current chat session.                                       |
| ScrapeWebPageHandler2         | HandlerV2           | Scrapes text from web pages.                                          |
| TasklistsManageHandler         | HandlerV2           | Manages persisted tasklists.                                          |
| TasklistsRunHandler            | HandlerV2           | Executes persisted tasklists.                                         |
| WebSearchHandler2              | HandlerV2           | Searches the web using Brave Search API.                               |

## 4. Source Files
| File                              | Responsibility                                           | Notable Exports                                                                 |
|-----------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                     | Package exports for handler implementations.            | Exports all handler classes for easy access.                                   |
| `chat2_handler.py`                | Manages chat session operations.                        | `Chat2Handler`                                                                  |
| `command_execution_handler2.py`   | Executes shell commands.                                | `CommandExecutionHandler2`                                                      |
| `curate_chat_handler.py`          | Curates chat sessions.                                 | `CurateChatHandler`                                                             |
| `delegate_tasks_handler.py`       | Manages task delegation.                               | `DelegateTasksHandler`                                                          |
| `embedding_handler.py`            | Generates and compares embeddings.                      | `EmbeddingHandler`                                                              |
| `file_load_handler2.py`           | Loads text files.                                      | `FileLoadHandler2`                                                              |
| `file_save_handler.py`            | Saves text files.                                      | `FileSaveHandler2`                                                              |
| `generate_doc_handler.py`         | Generates documentation for modules.                   | `GenerateDocHandler`                                                            |
| `generate_image_handler.py`       | Generates images.                                      | `GenerateImageHandler`                                                          |
| `generate_svg_handler.py`         | Validates and sanitizes SVG markup.                    | `GenerateSvgHandler`                                                            |
| `get_keywords_handler.py`         | Extracts keywords from text.                           | `GetKeywordsHandler`                                                            |
| `reset_session_handler.py`        | Resets chat sessions.                                  | `ResetSessionHandler`                                                           |
| `scrape_web_page_handler2.py`     | Scrapes text from web pages.                           | `ScrapeWebPageHandler2`                                                         |
| `tasklists_manage_handler.py`     | Manages tasklists.                                    | `TasklistsManageHandler`                                                        |
| `tasklists_run_handler.py`        | Executes tasklists.                                   | `TasklistsRunHandler`                                                           |
| `web_search_handler2.py`          | Searches the web.                                     | `WebSearchHandler2`                                                              |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `os`
  - `shlex`
  - `subprocess`
  - `re`
  - `io`
  - `hashlib`
  
- **Third-party packages**:
  - `requests`
  - `PIL` (Pillow)
  - `pydantic`
  
- **Internal modules**:
  - `src.config_manager`
  - `src.handlers.handler_v2`
  - `src.storage.json_file_storage`
  - `src.storage_paths.storage_paths`
  - `src.tasklists.task`
  - `src.tasklists.task_list`
  - `src.keywords.keywords`
  - `src.llm.interface`
  - `src.llm.router_api`
  
- **Optional dependencies**:
  - Handlers that depend on NLP libraries (spaCy, nltk, sklearn) are imported lazily.

## 6. Configuration / Settings
| Key                        | Type   | Default                       | What it controls                                      |
|----------------------------|--------|-------------------------------|------------------------------------------------------|
| `storage_root_path`       | string | `/home/junwin/lucydata`      | Base path for storage operations.                    |
| `storage_namespace`        | string | `data`                        | Namespace for storage operations.                    |
| `credential_path`          | string | `None`                       | Path to credentials for external services.           |
| `external_roots`          | dict   | `{}`                          | Mapping of external root keys to paths.              |
| `code_sandbox_path`       | string | `None`                       | Path for sandboxed execution.                        |
| `curation_llm_model`      | string | `gpt-4o-mini`                | Model used for curation tasks.                       |

## 7. Exceptions
| Exception                  | Base                | When Raised                                           |
|----------------------------|---------------------|------------------------------------------------------|
| `ValueError`               | Exception           | Raised for invalid arguments or configuration issues.|
| `FileNotFoundError`        | Exception           | Raised when a specified file cannot be found.       |
| `KeyError`                 | Exception           | Raised when an unknown handler is requested.        |
| `ValidationError`          | Exception           | Raised when input validation fails.                  |

## 8. Module-Level Constants
| Constant                   | Value               | Description                                           |
|----------------------------|---------------------|------------------------------------------------------|
| `BRAVE_ENDPOINT`           | `https://api.search.brave.com/res/v1/web/search` | Endpoint for Brave Search API.                       |
| `_ALLOWED_MIME_TYPES`      | Set of MIME types   | Allowed MIME types for images.                       |
| `_DEFAULT_MAX_DIMENSION`   | `512`                | Default maximum dimension for images.                |
| `_MAX_ALLOWED_DIMENSION`    | `512`                | Hard cap for maximum dimension to prevent overflow.  |

## 9. Methods (by class)
### Chat2Handler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Executes chat session management operations.                               |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### CommandExecutionHandler2
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Executes a command in a sandboxed environment.                            |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### CurateChatHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Executes chat curation operations.                                         |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### DelegateTasksHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Manages task delegation operations.                                        |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### EmbeddingHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Generates and compares embeddings.                                         |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### FileLoadHandler2
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Loads text files from specified locations.                                 |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### FileSaveHandler2
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Saves text files to specified locations.                                   |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### GenerateDocHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Generates documentation for Python modules.                                |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### GenerateImageHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Generates images and returns them as base64 data URIs.                    |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### GenerateSvgHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Validates and sanitizes SVG markup.                                        |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### GetKeywordsHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any]` | Extracts keywords from text.                                               |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### ResetSessionHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Resets the current chat session.                                           |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### ScrapeWebPageHandler2
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Scrapes text from web pages.                                              |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### TasklistsManageHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Manages persisted tasklists.                                              |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### TasklistsRunHandler
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]` | Executes persisted tasklists.                                             |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

### WebSearchHandler2
| Method                | Type        | Signature                                   | Description                                                                 |
|-----------------------|-------------|---------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`           | instance    | `def __init__(self, config: ConfigManager)` | Initializes the handler with configuration.                                |
| `execute`            | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]` | Searches the web using Brave Search API.                                   |
| `name`               | class       | `@classmethod def name(cls) -> str`       | Returns the name of the handler.                                           |
| `tool_def`           | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                              |

## 10. Usage Examples
### Chat2Handler
```python
from src.handlers import Chat2Handler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
chat_handler = Chat2Handler(config)

result = chat_handler.execute({
    "action": "get_session",
    "session_id": "12345"
})
print(result)
```

### CommandExecutionHandler2
```python
from src.handlers import CommandExecutionHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
command_handler = CommandExecutionHandler2(config)

result = command_handler.execute({
    "location": "sandbox",
    "command": "ls -la",
    "working_directory": "."
})
print(result)
```

### CurateChatHandler
```python
from src.handlers import CurateChatHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
curate_handler = CurateChatHandler(config)

result = curate_handler.execute({
    "session_id": "12345",
    "mode": "summarize",
    "publish": True
})
print(result)
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: Each handler implements robust error handling, returning structured error messages when exceptions occur. Handlers like `CommandExecutionHandler2` and `ScrapeWebPageHandler2` log detailed error messages for debugging.
- **Legacy Field Mapping**: Some handlers maintain backward compatibility by accepting legacy field names (e.g., `relative_path` in `FileLoadHandler2`).
- **Thread-Safety Concerns**: Handlers are designed to be stateless, making them inherently thread-safe. However, care should be taken when using shared resources like configuration files.
- **Known Limitations**: Handlers that depend on external services (e.g., `WebSearchHandler2`) may fail if the service is unavailable or if the API key is invalid.
- **Validation Logic**: Each handler uses Pydantic for input validation, ensuring that only well-structured data is processed.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| `src.main`                   | Imports various handlers for executing tasks.    |
| `src.api`                    | Uses handlers to process API requests.           |
| `src.cli`                    | CLI commands invoke handlers for specific tasks. |
| `src.tests`                  | Unit tests for handlers to ensure functionality. |

---

This document provides a comprehensive overview of the `src/handlers` module, detailing its structure, functionality, and usage.