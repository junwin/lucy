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
  - ResetSessionHandler
  - GetKeywordsHandler
  - GenerateImageHandler
  - GenerateSvgHandler
  - ServeImageHandler
  - TasklistsManageHandler
  - TasklistsRunHandler
  - SandboxExecuteHandler
---

## 1. Summary
The `src.handlers` module provides a collection of handler implementations for various tasks, including file operations, web scraping, command execution, and task management. These handlers are designed to be used in a larger system, allowing for modular and reusable components that can be invoked by agents or other parts of the application.

## 2. Key Classes

| Class                        | Base/Parent         | Purpose                                                  |
|------------------------------|---------------------|----------------------------------------------------------|
| FileLoadHandler2             | HandlerV2           | Loads text files from specified locations.               |
| FileSaveHandler2             | HandlerV2           | Saves text or code into files under specified locations. |
| CommandExecutionHandler2      | HandlerV2           | Executes shell commands in a controlled environment.     |
| ScrapeWebPageHandler2        | HandlerV2           | Scrapes text from web pages.                             |
| WebSearchHandler2            | HandlerV2           | Performs web searches using the Brave Search API.        |
| DelegateTasksHandler         | HandlerV2           | Plans and delegates tasks for execution.                 |
| Chat2Handler                 | HandlerV2           | Manages chat sessions and events.                        |
| CurateChatHandler            | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving. |
| GenerateDocHandler           | HandlerV2           | Generates documentation for Python modules.              |
| ResetSessionHandler          | HandlerV2           | Resets the current chat session.                         |
| GetKeywordsHandler           | HandlerV2           | Extracts keywords from text content.                     |
| GenerateImageHandler         | HandlerV2           | Generates simple images and returns them as base64.     |
| GenerateSvgHandler           | HandlerV2           | Validates and sanitizes SVG markup.                      |
| ServeImageHandler            | HandlerV2           | Serves images as base64 data URIs.                       |
| TasklistsManageHandler       | HandlerV2           | Manages persisted task lists (CRUD operations).          |
| TasklistsRunHandler          | HandlerV2           | Executes persisted task lists.                           |
| SandboxExecuteHandler        | HandlerV2           | Executes a sequence of tool calls in one batch.         |

## 3. Source Files

| File                             | Responsibility                                      | Notable Exports                                                                 |
|----------------------------------|----------------------------------------------------|---------------------------------------------------------------------------------|
| __init__.py                      | Package exports for handler implementations.       | FileLoadHandler2, FileSaveHandler2, CommandExecutionHandler2, ...             |
| chat2_handler.py                 | Manages chat sessions and events.                  | Chat2Handler                                                                    |
| command_execution_handler2.py    | Executes shell commands.                           | CommandExecutionHandler2                                                         |
| curate_chat_handler.py           | Curates chat sessions.                             | CurateChatHandler                                                               |
| delegate_tasks_handler.py        | Plans and delegates tasks.                         | DelegateTasksHandler                                                            |
| file_load_handler2.py           | Loads files from specified locations.              | FileLoadHandler2                                                                |
| file_save_handler.py             | Saves files to specified locations.                | FileSaveHandler2                                                                |
| generate_doc_handler.py          | Generates documentation for modules.               | GenerateDocHandler                                                              |
| generate_image_handler.py        | Generates images and returns them as base64.      | GenerateImageHandler                                                            |
| generate_svg_handler.py          | Validates and sanitizes SVG markup.                | GenerateSvgHandler                                                              |
| get_keywords_handler.py          | Extracts keywords from text.                       | GetKeywordsHandler                                                              |
| reset_session_handler.py         | Resets the current chat session.                   | ResetSessionHandler                                                             |
| scrape_web_page_handler2.py      | Scrapes text from web pages.                       | ScrapeWebPageHandler2                                                           |
| serve_image_handler.py           | Serves images as base64 data URIs.                 | ServeImageHandler                                                               |
| tasklists_manage_handler.py      | Manages persisted task lists.                      | TasklistsManageHandler                                                          |
| tasklists_run_handler.py         | Executes persisted task lists.                     | TasklistsRunHandler                                                             |
| sandbox_execute_handler.py       | Executes a sequence of tool calls.                | SandboxExecuteHandler                                                           |
| web_search_handler2.py          | Performs web searches.                             | WebSearchHandler2                                                               |

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
  - src.llm.interface
  - src.llm.router_api

## 5. Methods (by class)

### FileLoadHandler2

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Loads a text file from a specified location.                              |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### FileSaveHandler2

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Saves content to a specified file.                                         |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### CommandExecutionHandler2

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes a command in a sandboxed environment.                            |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### ScrapeWebPageHandler2

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Scrapes text from a specified web page.                                   |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### WebSearchHandler2

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Performs a web search using the Brave Search API.                         |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### DelegateTasksHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Plans and delegates tasks for execution.                                   |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### Chat2Handler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Manages chat sessions and events.                                          |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### CurateChatHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Curates chat sessions by filtering, summarizing, or archiving.            |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### GenerateDocHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Generates documentation for Python modules.                                |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### ResetSessionHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Resets the current chat session.                                           |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### GetKeywordsHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Extracts keywords from text content.                                       |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### GenerateImageHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Generates images and returns them as base64.                              |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### GenerateSvgHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Validates and sanitizes SVG markup.                                        |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### ServeImageHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Serves images as base64 data URIs.                                         |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### TasklistsManageHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Manages persisted task lists (CRUD operations).                            |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### TasklistsRunHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes a persisted task list.                                            |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |

### SandboxExecuteHandler

| Method         | Type        | Signature                                      | Description                                                                 |
|----------------|-------------|------------------------------------------------|-----------------------------------------------------------------------------|
| execute        | instance    | def execute(self, args: Dict[str, Any], ...) | Executes a sequence of tool calls in one batch.                           |
| execute_raw    | instance    | def execute_raw(self, arguments_raw: str, ...) | Executes with raw JSON arguments.                                          |
```