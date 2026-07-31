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
The `src/handlers` module provides a collection of handler classes that facilitate various operations within the Lucy project. Each handler implements the `HandlerV2` interface, allowing for structured interactions with external services, file operations, and task management. The module is designed to support a wide range of functionalities, including web scraping, file handling, task delegation, and session management, thereby enabling the core functionalities of the Lucy project.

This module fits into the overall architecture as a key component that interacts with both external APIs and internal data storage, allowing for seamless integration of various functionalities. It solves the problem of managing complex workflows by providing a consistent interface for executing tasks, handling files, and interacting with web services.

## 2. Architecture & Design
The `src/handlers` module employs several design patterns and principles:

- **Handler Pattern**: Each handler class implements the `HandlerV2` interface, ensuring a consistent method signature and behavior across different handlers.
- **Dependency Injection**: Handlers receive configuration through the `ConfigManager`, allowing for flexible configuration management.
- **Error Handling**: Each handler includes robust error handling, returning structured error messages to facilitate debugging and user feedback.
- **Separation of Concerns**: Each handler is responsible for a specific functionality, promoting modularity and ease of maintenance.

The handlers are designed to be extensible, allowing for the addition of new functionalities without modifying existing code. This modular approach is evident in the way handlers are registered and instantiated through the `HandlerRegistry`.

## 3. Key Classes
| Class                          | Base/Parent            | Purpose                                                                 |
|--------------------------------|------------------------|-------------------------------------------------------------------------|
| `Chat2Handler`                 | `HandlerV2`            | Manages chat sessions with CRUD operations.                             |
| `CommandExecutionHandler2`     | `HandlerV2`            | Executes commands in a sandboxed environment.                          |
| `CurateChatHandler`            | `HandlerV2`            | Curates chat sessions by filtering, summarizing, or archiving events.  |
| `DelegateTasksHandler`         | `HandlerV2`            | Plans and delegates tasks for a goal.                                  |
| `FileLoadHandler2`             | `HandlerV2`            | Loads text files from specified locations.                             |
| `FileSaveHandler2`             | `HandlerV2`            | Saves text files to specified locations.                               |
| `GenerateDocHandler`           | `HandlerV2`            | Generates documentation for Python modules using LLM.                 |
| `GenerateImageHandler`         | `HandlerV2`            | Generates simple images and returns them as base64 data URIs.         |
| `GenerateSvgHandler`           | `HandlerV2`            | Validates and sanitizes SVG markup.                                    |
| `GetKeywordsHandler`           | `HandlerV2`            | Extracts keywords from text.                                           |
| `ResetSessionHandler`          | `HandlerV2`            | Resets the current chat session.                                       |
| `ScrapeWebPageHandler2`        | `HandlerV2`            | Scrapes text from web pages.                                          |
| `TasklistsManageHandler`       | `HandlerV2`            | Manages persisted tasklists (CRUD operations).                        |
| `TasklistsRunHandler`          | `HandlerV2`            | Executes a persisted tasklist.                                        |
| `WebSearchHandler2`            | `HandlerV2`            | Searches the web using Brave Search API.                               |

## 4. Source Files
| File                              | Responsibility                                         | Notable Exports                                                                 |
|-----------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                     | Package exports for handler implementations.          | Exports all handler classes for easy access.                                   |
| `chat2_handler.py`                | Manages chat sessions.                               | `Chat2Handler`                                                                  |
| `command_execution_handler2.py`   | Executes commands in a sandbox.                     | `CommandExecutionHandler2`                                                      |
| `curate_chat_handler.py`          | Curates chat sessions.                               | `CurateChatHandler`                                                             |
| `delegate_tasks_handler.py`       | Plans and delegates tasks.                           | `DelegateTasksHandler`                                                          |
| `file_load_handler2.py`           | Loads text files.                                   | `FileLoadHandler2`                                                              |
| `file_save_handler.py`            | Saves text files.                                   | `FileSaveHandler2`                                                              |
| `generate_doc_handler.py`         | Generates documentation for modules.                | `GenerateDocHandler`                                                            |
| `generate_image_handler.py`       | Generates images and returns them as base64.       | `GenerateImageHandler`                                                          |
| `generate_svg_handler.py`         | Validates and sanitizes SVG markup.                 | `GenerateSvgHandler`                                                            |
| `get_keywords_handler.py`         | Extracts keywords from text.                         | `GetKeywordsHandler`                                                            |
| `reset_session_handler.py`        | Resets the current chat session.                    | `ResetSessionHandler`                                                           |
| `scrape_web_page_handler2.py`     | Scrapes text from web pages.                        | `ScrapeWebPageHandler2`                                                         |
| `tasklists_manage_handler.py`     | Manages persisted tasklists.                        | `TasklistsManageHandler`                                                        |
| `tasklists_run_handler.py`        | Executes persisted tasklists.                       | `TasklistsRunHandler`                                                           |
| `web_search_handler2.py`          | Searches the web using Brave Search API.            | `WebSearchHandler2`                                                              |

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
  - `mimetypes`
  
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
  - `src.tasklists.task_states`
  
- **Optional dependencies**:
  - `spaCy`
  - `nltk`
  - `sklearn`

## 6. Configuration / Settings
| Key                        | Type   | Default                       | What it controls                                      |
|---------------------------|--------|-------------------------------|------------------------------------------------------|
| `storage_root_path`       | string | None                          | Root path for storage operations.                    |
| `storage_namespace`        | string | None                          | Namespace for storage operations.                     |
| `credential_path`         | string | None                          | Path to credentials for external services.           |
| `code_sandbox_path`       | string | None                          | Base path for sandboxed operations.                  |
| `external_roots`          | dict   | {}                            | Mapping of external root keys to paths.              |
| `curation_llm_model`      | string | "gpt-4o-mini"                | Model used for LLM-based curation.                   |

## 7. Exceptions
| Exception                  | Base                | When Raised                                                  |
|----------------------------|---------------------|------------------------------------------------------------|
| None                       | None                | No custom exceptions defined in this module.               |

## 8. Module-Level Constants
| Constant                   | Value               | Description                                                |
|----------------------------|---------------------|------------------------------------------------------------|
| `_DEFAULT_MAX_DIMENSION`   | 512                 | Default maximum dimension for images in pixels.           |

## 9. Methods (by class)
### Chat2Handler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Executes chat session management operations.                               |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### CommandExecutionHandler2
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Executes a command in a sandboxed environment.                             |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### CurateChatHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Executes chat curation operations.                                         |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### DelegateTasksHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Plans and delegates tasks for a goal.                                      |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### FileLoadHandler2
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Loads a text file from specified locations.                                |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### FileSaveHandler2
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Saves a text file to specified locations.                                  |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### GenerateDocHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Generates documentation for modules.                                       |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### GenerateImageHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Generates images and returns them as base64 data URIs.                    |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### GenerateSvgHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Validates and sanitizes SVG markup.                                        |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### GetKeywordsHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any]` | Extracts keywords from text.                                               |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### ResetSessionHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]` | Resets the current chat session.                                           |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### ScrapeWebPageHandler2
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Scrapes text from web pages.                                              |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### TasklistsManageHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]` | Manages persisted tasklists (CRUD operations).                             |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### TasklistsRunHandler
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]` | Executes a persisted tasklist.                                            |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

### WebSearchHandler2
| Method                     | Type        | Signature                                      | Description                                                                 |
|----------------------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, config: ConfigManager)`  | Initializes the handler with the given configuration.                      |
| `execute`                  | instance    | `def execute(self, args: Dict[str, Any], *, account_name: str = "auto")` | Searches the web using Brave Search API.                                   |
| `name`                     | class       | `@classmethod def name(cls) -> str`          | Returns the name of the handler.                                          |
| `tool_def`                 | class       | `@classmethod def tool_def(cls) -> Dict[str, Any]` | Returns the tool definition for the handler.                               |

## 10. Usage Examples
### Chat2Handler
```python
from src.handlers import Chat2Handler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
chat_handler = Chat2Handler(config)
result = chat_handler.execute({"action": "get_session", "session_id": "12345"})
```

### CommandExecutionHandler2
```python
from src.handlers import CommandExecutionHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
command_handler = CommandExecutionHandler2(config)
result = command_handler.execute({"command": "ls", "location": "sandbox", "working_directory": "."})
```

### CurateChatHandler
```python
from src.handlers import CurateChatHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
curate_handler = CurateChatHandler(config)
result = curate_handler.execute({"session_id": "12345", "mode": "summarize"})
```

### DelegateTasksHandler
```python
from src.handlers import DelegateTasksHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
delegate_handler = DelegateTasksHandler(config)
result = delegate_handler.execute({"goal": "Refactor code", "files": ["file1.py", "file2.py"], "instruction": "Refactor the following files."})
```

### FileLoadHandler2
```python
from src.handlers import FileLoadHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
file_load_handler = FileLoadHandler2(config)
result = file_load_handler.execute({"location": "storage", "external_root": "", "path": "data.txt"})
```

### FileSaveHandler2
```python
from src.handlers import FileSaveHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
file_save_handler = FileSaveHandler2(config)
result = file_save_handler.execute({"location": "storage", "external_root": "", "path": "output.txt", "file_content": "Hello, World!"})
```

### GenerateDocHandler
```python
from src.handlers import GenerateDocHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
doc_handler = GenerateDocHandler(config)
result = doc_handler.execute({"module_path": "src/handlers", "output_path": "docs/handlers.md", "doc_type": "full", "instructions": ""})
```

### GenerateImageHandler
```python
from src.handlers import GenerateImageHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
image_handler = GenerateImageHandler(config)
result = image_handler.execute({"description": "A simple rectangle", "width": 400, "height": 200, "color": "#ff0000"})
```

### GenerateSvgHandler
```python
from src.handlers import GenerateSvgHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
svg_handler = GenerateSvgHandler(config)
result = svg_handler.execute({"svg_code": "<svg><circle cx='50' cy='50' r='40' fill='red' /></svg>", "description": "A red circle", "width": 100, "height": 100})
```

### GetKeywordsHandler
```python
from src.handlers import GetKeywordsHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
keywords_handler = GetKeywordsHandler(config)
result = keywords_handler.execute({"content": "This is a sample text for keyword extraction.", "top_n": 5, "language_code": "en"})
```

### ResetSessionHandler
```python
from src.handlers import ResetSessionHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
reset_handler = ResetSessionHandler(config)
result = reset_handler.execute({}, account_name="user123", conversation_id="12345")
```

### ScrapeWebPageHandler2
```python
from src.handlers import ScrapeWebPageHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
scrape_handler = ScrapeWebPageHandler2(config)
result = scrape_handler.execute({"page_url": "https://example.com"})
```

### TasklistsManageHandler
```python
from src.handlers import TasklistsManageHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
tasklist_handler = TasklistsManageHandler(config)
result = tasklist_handler.execute({"action": "list", "tasklist_name": "", "tasklist": {}, "validate_only": False})
```

### TasklistsRunHandler
```python
from src.handlers import TasklistsRunHandler
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
run_handler = TasklistsRunHandler(config)
result = run_handler.execute({"tasklist_id": "tasklist_123", "mode": "multi-step"}, account_name="user123")
```

### WebSearchHandler2
```python
from src.handlers import WebSearchHandler2
from src.config_manager import ConfigManager

config = ConfigManager("config.json")
web_search_handler = WebSearchHandler2(config)
result = web_search_handler.execute({"query": "OpenAI", "count": 5})
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: Each handler implements robust error handling, returning structured error messages. Handlers should be designed to fail gracefully, providing meaningful feedback to the caller.
- **Legacy Field Mapping**: Some handlers may have legacy field mappings (e.g., `relative_path` in `FileLoadHandler2`), which should be documented and handled appropriately.
- **Thread-Safety Concerns**: Handlers that modify shared state (e.g., task lists) should ensure thread safety, especially in multi-threaded environments.
- **Known Limitations**: Some handlers may have limitations based on external dependencies (e.g., `GetKeywordsHandler` requires NLP libraries).
- **Validation Logic**: Handlers should validate input parameters thoroughly to prevent unexpected behavior or errors during execution.

## 12. Consumers
| Consumer                     | What it uses                                           |
|------------------------------|-------------------------------------------------------|
| Various modules in the project | Imports specific handlers for task execution, file management, and web interactions. |
| FunctionCallingProcessor      | Calls handlers to manage tasks and sessions.         |
| AutomationProcessor           | Uses task management handlers to execute task lists. |