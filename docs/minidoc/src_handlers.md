```markdown
---
tags:
  - src_handlers
  - lucyproject
  - FileLoadHandler2
  - FileSaveHandler2
  - CommandExecutionHandler2
  - ScrapeWebPageHandler2
  - WebSearchHandler2
  - DelegateTasksHandler
  - Chat2Handler
  - CurateChatHandler
  - GenerateDocHandler
  - SandboxExecuteHandler
  - ResetSessionHandler
  - ServeImageHandler
  - GenerateSvgHandler
  - EmbeddingHandler
  - GetKeywordsHandler
  - TasklistsManageHandler
  - TasklistsRunHandler
---

## 1. Summary
The `src.handlers` module provides a collection of handler implementations for various tasks, including file operations, web scraping, command execution, chat management, and task delegation. These handlers are designed to be used in a larger system, allowing for modular and reusable components that can be invoked by agents or other parts of the application.

## 2. Key Classes

| Class                        | Base/Parent         | Purpose                                                  |
|------------------------------|---------------------|----------------------------------------------------------|
| FileLoadHandler2             | HandlerV2           | Loads text files from specified locations.               |
| FileSaveHandler2             | HandlerV2           | Saves text files to specified locations.                 |
| CommandExecutionHandler2      | HandlerV2           | Executes shell commands in a controlled environment.     |
| ScrapeWebPageHandler2        | HandlerV2           | Scrapes text content from web pages.                     |
| WebSearchHandler2            | HandlerV2           | Performs web searches using the Brave Search API.        |
| DelegateTasksHandler         | HandlerV2           | Manages task delegation for sequential task execution.   |
| Chat2Handler                 | HandlerV2           | Manages chat sessions and events.                        |
| CurateChatHandler            | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving. |
| GenerateDocHandler           | HandlerV2           | Generates documentation for Python modules.              |
| SandboxExecuteHandler        | HandlerV2           | Executes a sequence of tool calls in a sandboxed environment. |
| ResetSessionHandler          | HandlerV2           | Resets the current chat session.                         |
| ServeImageHandler            | HandlerV2           | Serves image files as base64-encoded data URIs.         |
| GenerateSvgHandler           | HandlerV2           | Validates and sanitizes SVG markup.                     |
| EmbeddingHandler             | HandlerV2           | Generates and compares vector embeddings.                |
| GetKeywordsHandler           | HandlerV2           | Extracts keywords from text content.                     |
| TasklistsManageHandler       | HandlerV2           | Manages persisted tasklists (CRUD operations).          |
| TasklistsRunHandler          | HandlerV2           | Executes persisted tasklists.                            |

## 3. Source Files

| File                             | Responsibility                                      | Notable Exports                                      |
|----------------------------------|----------------------------------------------------|-----------------------------------------------------|
| __init__.py                      | Package exports for handler implementations.        | All handlers listed in the module.                  |
| chat2_handler.py                 | Manages chat sessions.                             | Chat2Handler                                         |
| command_execution_handler2.py    | Executes shell commands.                           | CommandExecutionHandler2                             |
| curate_chat_handler.py           | Curates chat sessions.                             | CurateChatHandler                                    |
| delegate_tasks_handler.py        | Manages task delegation.                           | DelegateTasksHandler                                 |
| embedding_handler.py             | Generates and compares embeddings.                 | EmbeddingHandler                                     |
| file_load_handler2.py            | Loads files from specified locations.              | FileLoadHandler2                                     |
| file_save_handler.py             | Saves files to specified locations.                | FileSaveHandler2                                     |
| generate_doc_handler.py          | Generates documentation for modules.               | GenerateDocHandler                                   |
| generate_image_handler.py        | Generates images and returns them as base64.      | GenerateImageHandler                                  |
| generate_svg_handler.py          | Validates and sanitizes SVG markup.                | GenerateSvgHandler                                   |
| get_keywords_handler.py          | Extracts keywords from text.                       | GetKeywordsHandler                                   |
| reset_session_handler.py         | Resets chat sessions.                              | ResetSessionHandler                                  |
| scrape_web_page_handler2.py      | Scrapes web pages for content.                     | ScrapeWebPageHandler2                                |
| serve_image_handler.py           | Serves images as base64 data URIs.                | ServeImageHandler                                    |
| tasklists_manage_handler.py      | Manages tasklists (CRUD operations).               | TasklistsManageHandler                               |
| tasklists_run_handler.py         | Executes persisted tasklists.                      | TasklistsRunHandler                                  |
| web_search_handler2.py           | Performs web searches.                             | WebSearchHandler2                                    |

## 4. Dependencies

- **Standard library**
  - json
  - logging
  - os
  - re
  - subprocess
  - typing
  - urllib

- **Third-party packages**
  - requests
  - Pillow
  - Pydantic

- **Internal modules**
  - src.config_manager
  - src.handlers.handler_v2
  - src.storage.json_file_storage
  - src.storage_paths.storage_paths
  - src.tasklists.task
  - src.tasklists.task_list
  - src.tasklists.task_states
  - src.keywords.keywords
  - src.embeddings
  - src.llm.interface
  - src.llm.router_api

## 5. Methods (by class)

### FileLoadHandler2

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Loads a text file from a specified location.     |

### FileSaveHandler2

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Saves a text file to a specified location.       |

### CommandExecutionHandler2

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes a command in a controlled environment.  |

### ScrapeWebPageHandler2

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Scrapes text content from a web page.            |

### WebSearchHandler2

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Performs a web search using the Brave Search API. |

### DelegateTasksHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Manages task delegation for sequential execution. |

### Chat2Handler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Manages chat sessions and events.                |

### CurateChatHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Curates chat sessions by filtering or summarizing. |

### GenerateDocHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Generates documentation for Python modules.      |

### SandboxExecuteHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes a sequence of tool calls in a sandboxed environment. |

### ResetSessionHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Resets the current chat session.                 |

### ServeImageHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Serves image files as base64-encoded data URIs. |

### GenerateSvgHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Validates and sanitizes SVG markup.              |

### EmbeddingHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Generates and compares vector embeddings.        |

### GetKeywordsHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Extracts keywords from text content.             |

### TasklistsManageHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Manages persisted tasklists (CRUD operations).  |

### TasklistsRunHandler

| Method         | Type        | Signature                                      | Description                                      |
|----------------|-------------|------------------------------------------------|--------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes persisted tasklists.                    |
```