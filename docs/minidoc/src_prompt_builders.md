# Module Documentation for `src/prompt_builders`

## YAML Front Matter
```yaml
tags:
  - src_prompt_builders
  - lucyproject
  - PromptBuilder
  - PromptBuilderInterface
```

## 1. Summary
The `src/prompt_builders` module is responsible for constructing prompts for AI models, particularly in the context of chat-based interactions. It provides a structured way to gather and format user input, historical chat data, and contextual information into a format suitable for model consumption. This module fits into the overall architecture by serving as a bridge between user interactions and the AI model, ensuring that the prompts generated are rich in context and relevant to the ongoing conversation. The primary problem it solves is the need for a coherent and contextually aware prompt generation mechanism that can handle various input types and sources.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Abstract Base Class (ABC)**: The `PromptBuilderInterface` defines a contract for prompt builders, ensuring that any implementation adheres to a specific interface.
- **Dependency Injection**: The `PromptBuilder` class uses dependency injection to receive its dependencies (like `AgentManager`, `ConfigManager`, etc.), promoting loose coupling and easier testing.

The `PromptBuilder` class implements the `PromptBuilderInterface`, adhering to the contract defined by the abstract class. It utilizes composition to integrate various components, such as the `AgentManager` for agent-related data and the `Storage` for context retrieval.

There is no explicit legacy/v2 split in the code, but the design choices reflect a focus on modularity and extensibility, allowing for future enhancements without significant refactoring.

Key design decisions include:
- Logging at various stages of prompt building to facilitate debugging and monitoring.
- Soft error handling, where the system continues to function even if certain context or document retrievals fail.

## 3. Key Classes
| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| `PromptBuilder`           | `PromptBuilderInterface`    | Constructs prompts for AI models using various contextual inputs.       |
| `PromptBuilderInterface`  | `ABC`                      | Defines the interface for prompt builders, ensuring consistent behavior. |

## 4. Source Files
| File                                      | Responsibility                                         | Notable Exports                     |
|-------------------------------------------|-------------------------------------------------------|-------------------------------------|
| `src/prompt_builders/__init__.py`        | Initializes the package.                              | None                                |
| `src/prompt_builders/prompt_builder.py`  | Implements the `PromptBuilder` class and its methods.| `PromptBuilder`, `estimate_tokens_from_text` |
| `src/prompt_builders/prompt_builder_interface.py` | Defines the `PromptBuilderInterface`.                 | `PromptBuilderInterface`, `ChatMessageDict` |

## 5. Dependencies
- **Standard library**:
  - `base64`
  - `glob`
  - `logging`
  - `os`
  - `datetime`
  - `typing`
  
- **Third-party packages**:
  - `injector`
  
- **Internal modules**:
  - `src.config_manager`
  - `src.agent`
  - `src.storage.base`
  - `src.prompt_builders.prompt_builder_interface`
  - `src.utils.document_context`
  - `src.chat2.facade`
  - `src.chat2.prompt_slice`
  
- **Optional dependencies**: None.

## 6. Configuration / Settings
| Key                        | Type   | Default                               | What it controls                     |
|----------------------------|--------|---------------------------------------|--------------------------------------|
| `storage_root_path`       | String | `/home/junwin/lucy_storage`          | Base path for storage.               |
| `storage_namespace`        | String | `data`                                | Namespace for storage organization.   |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      |      | None        |

## 8. Module-Level Constants
| Constant                        | Value   | Description                                      |
|---------------------------------|---------|--------------------------------------------------|
| `DEFAULT_PROMPT_BUDGET_TOKENS` | 12000   | Default token budget for prompts.                |
| `DEFAULT_SOURCE_BUDGETS`        | Dict    | Default budget allocation for different sources. |

## 9. Methods (by class)

### `PromptBuilder`
| Method                | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|-----------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`            | Instance     | `def __init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, chat2_store: Optional[Chat2Store] = None)` | Initializes the `PromptBuilder` with necessary dependencies. Accepts instances of `AgentManager`, `ConfigManager`, `Storage`, and an optional `Chat2Store`.                                                                                                                                                                            |
| `build_prompt`        | Instance     | `def build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]` | Constructs a prompt for the AI model. It gathers context from various sources, including chat history and external documents, and formats them into a structured list of messages. Key parameters include `content_text`, `conversation_id`, `agent_name`, and `account_name`. Returns a list of message dictionaries. Handles logging and error conditions gracefully. |
| `_build_agent_system_message` | Instance     | `def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str` | Constructs a system message for the agent based on its properties. Returns a string that combines the agent's system prompt, persona, and style prompt.                                                                                                                                                                                      |
| `_resolve_attachments` | Instance     | `def _resolve_attachments(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]]) -> List[Dict[str, Any]]` | Resolves image and file IDs into a format suitable for the prompt. Returns a list of content parts, including base64-encoded images and text from files. Handles errors and logs warnings if files are not found.                                                                                                                                 |
| `_build_images_dir`    | Instance     | `def _build_images_dir(self) -> str`                                   | Returns the base directory path for images based on configuration settings.                                                                                                                                                                                                                                                                  |
| `_find_image_file`     | Instance     | `def _find_image_file(self, images_dir: str, account_name: str, img_id: str) -> Optional[str]` | Searches for an image file by its ID in the specified directory. Returns the file path if found, or None if not.                                                                                                                                                                                                                             |
| `_find_file`           | Instance     | `def _find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str]` | Searches for a general file by its ID in the specified directory. Currently delegates to `_find_image_file`.                                                                                                                                                                                                                                 |
| `_guess_mime_from_path`| Static       | `def _guess_mime_from_path(path: str) -> str`                          | Guesses the MIME type of a file based on its extension. Returns a string representing the MIME type.                                                                                                                                                                                                                                        |
| `_get_chat_history_messages` | Instance | `def _get_chat_history_messages(self, conversation_id: str, account_name: str, agent_name: str, max_conversations: int) -> List[Dict[str, str]]` | Retrieves chat history messages for a given conversation ID. Returns a list of message dictionaries. Handles errors and logs warnings if retrieval fails.                                                                                                                                                                                  |
| `_get_context_state`   | Instance     | `def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]` | Retrieves the context state for a given account and context name. Returns the context object or None if not found.                                                                                                                                                                                                                          |
| `_get_context_text`    | Instance     | `def _get_context_text(self, account_name: str, context_name: str) -> str` | Loads context text from storage, including any imported skills. Returns the context text as a string.                                                                                                                                                                                                                                       |
| `_ensure_current_query` | Instance     | `def _ensure_current_query(self, messages: List[Dict[str, Any]], current_query: str) -> List[Dict[str, Any]]` | Ensures that the current user query is included in the messages list. Returns the updated messages list.                                                                                                                                                                                                                                     |

## 10. Usage Examples
```python
from src.prompt_builders.prompt_builder import PromptBuilder

# Assuming necessary dependencies are instantiated
prompt_builder = PromptBuilder(agent_manager, config, storage, chat2_store)

# Building a prompt
messages = prompt_builder.build_prompt(
    content_text="What is the weather like today?",
    conversation_id="12345",
    agent_name="WeatherAgent",
    account_name="UserAccount"
)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-soft approach, logging warnings when certain data cannot be retrieved (e.g., missing images or files) but continuing execution.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken if used in a multi-threaded environment.
- **Context Handling**: If the context is missing, it creates a new one with default values, which may lead to unexpected behavior if not managed properly.
- **MIME Type Guessing**: The `_guess_mime_from_path` method may not cover all file types, leading to potential issues with unsupported formats.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|---------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |