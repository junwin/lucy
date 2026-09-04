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
  - ServeImageHandler
  - ContextHandler
---

## 1. Summary
The `src/handlers` module provides a collection of handler implementations for various tasks within the Lucy project. These handlers facilitate operations such as file management, web scraping, command execution, chat session management, and more. Each handler adheres to a standardized interface, allowing for seamless integration and interaction with the underlying system.

## 2. Key Classes

| Class                          | Base/Parent         | Purpose                                                                 |
|--------------------------------|---------------------|-------------------------------------------------------------------------|
| FileLoadHandler2               | HandlerV2           | Loads text files from specified locations.                              |
| FileSaveHandler2               | HandlerV2           | Saves text or code into files under specified locations.               |
| CommandExecutionHandler2       | HandlerV2           | Executes system commands in a controlled environment.                  |
| ScrapeWebPageHandler2          | HandlerV2           | Scrapes text content from web pages.                                   |
| WebSearchHandler2              | HandlerV2           | Performs web searches using the Brave Search API.                      |
| Chat2Handler                   | HandlerV2           | Manages chat sessions for agents.                                      |
| ResetSessionHandler            | HandlerV2           | Resets the current chat session.                                       |
| RemoteExecuteHandler           | HandlerV2           | Sends queries to a remote Lucy instance.                               |
| ToolHandlerMetaHandler         | HandlerV2           | Provides metadata for registered tools.                                |
| AgentsManageHandler            | HandlerV2           | Manages agent definitions at runtime.                                  |
| GetKeywordsHandler             | HandlerV2           | Extracts keywords from text.                                           |
| CurateChatHandler              | HandlerV2           | Curates chat sessions by filtering, summarizing, or archiving events.  |
| GenerateDocHandler             | HandlerV2           | Generates documentation for Python modules.                            |
| GenerateImageHandler           | HandlerV2           | Generates simple images and returns them as base64 data URIs.         |
| GenerateSvgHandler             | HandlerV2           | Validates and sanitizes SVG markup.                                    |
| EmbeddingHandler               | HandlerV2           | Generates and compares vector embeddings.                               |
| TasklistsManageHandler         | HandlerV2           | Manages tasklists and tasks.                                           |
| TasklistsRunHandler            | HandlerV2           | Executes persisted tasklists.                                          |
| LazyToolSelectorHandler        | HandlerV2           | Probes lazy tool loading and reports token savings.                    |
| ToolSelectionProbeHandler      | HandlerV2           | Diagnoses the tool selection pipeline.                                  |
| ServeImageHandler              | HandlerV2           | Serves images as base64 data URIs.                                     |
| ContextHandler                 | HandlerV2           | Manages conversation contexts stored as Markdown + YAML.               |

## 3. Source Files

| File                              | Responsibility                                         | Notable Exports                                                                 |
|-----------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| __init__.py                       | Package exports for handler implementations.          | FileLoadHandler2, FileSaveHandler2, CommandExecutionHandler2, ...             |
| agents_manage_handler.py          | Manages agent definitions at runtime.                | AgentsManageHandler                                                             |
| chat2_handler.py                  | Manages chat sessions for agents.                    | Chat2Handler                                                                    |
| command_execution_handler2.py     | Executes system commands.                             | CommandExecutionHandler2                                                        |
| curate_chat_handler.py            | Curates chat sessions.                               | CurateChatHandler                                                               |
| embedding_handler.py              | Generates and compares embeddings.                    | EmbeddingHandler                                                                |
| file_load_handler2.py             | Loads text files.                                    | FileLoadHandler2                                                                |
| file_save_handler.py              | Saves text or code into files.                       | FileSaveHandler2                                                                |
| generate_doc_handler.py           | Generates documentation for modules.                 | GenerateDocHandler                                                              |
| generate_image_handler.py         | Generates images and returns them as base64.        | GenerateImageHandler                                                            |
| generate_svg_handler.py           | Validates and sanitizes SVG markup.                  | GenerateSvgHandler                                                              |
| remote_execute_handler.py         | Queries a remote Lucy instance.                      | RemoteExecuteHandler                                                            |
| reset_session_handler.py          | Resets the current chat session.                     | ResetSessionHandler                                                             |
| scrape_web_page_handler2.py       | Scrapes web pages for text content.                  | ScrapeWebPageHandler2                                                           |
| serve_image_handler.py            | Serves images as base64 data URIs.                   | ServeImageHandler                                                               |
| tasklists_manage_handler.py       | Manages tasklists and tasks.                         | TasklistsManageHandler                                                          |
| tasklists_run_handler.py          | Executes persisted tasklists.                        | TasklistsRunHandler                                                             |
| tool_handler_meta_handler.py      | Provides metadata for tools.                         | ToolHandlerMetaHandler                                                          |
| web_search_handler2.py            | Performs web searches.                               | WebSearchHandler2                                                               |
| lazy_tool_selector_handler.py      | Probes lazy tool loading.                            | LazyToolSelectorHandler                                                         |
| tool_selection_probe_handler.py    | Diagnoses the tool selection pipeline.               | ToolSelectionProbeHandler                                                       |

## 4. Dependencies

- **Standard library**
  - json
  - logging
  - os
  - re
  - subprocess
  - sys
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
  - src.tool_selection

## 5. Methods (by class)

### FileLoadHandler2

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Loads a text file's contents and returns them. |

### FileSaveHandler2

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Saves code or text into a file under a named location. |

### CommandExecutionHandler2

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Runs a command under a named location. |

### ScrapeWebPageHandler2

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Reads the text from a webpage. |

### WebSearchHandler2

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Uses Brave Search to search the web. |

### Chat2Handler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Manages chat sessions for agents. |

### ResetSessionHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Resets the current chat session. |

### RemoteExecuteHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Sends a query to a remote Lucy instance. |

### ToolHandlerMetaHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Returns tool metadata for registered handlers. |

### AgentsManageHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any] | Manages agent definitions at runtime. |

### GetKeywordsHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any] | Extracts keywords from a string. |

### CurateChatHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Curates chat sessions. |

### GenerateDocHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Generates documentation for a module. |

### GenerateImageHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Generates simple images and returns them as base64 data URIs. |

### GenerateSvgHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Validates and sanitizes SVG markup. |

### EmbeddingHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Generates and compares vector embeddings. |

### TasklistsManageHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Manages tasklists and tasks. |

### TasklistsRunHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Executes persisted tasklists. |

### LazyToolSelectorHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Probes lazy tool loading and reports token savings. |

### ToolSelectionProbeHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any] | Diagnoses the tool selection pipeline. |

### ServeImageHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any] | Serves images as base64 data URIs. |

### ContextHandler

| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| execute | instance     | def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any] | Manages conversation contexts stored as Markdown + YAML. |

```