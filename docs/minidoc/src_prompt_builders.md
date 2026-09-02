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
The `src/prompt_builders` module is responsible for constructing prompts for AI models, particularly in the context of conversational agents. It provides a structured way to build prompts by integrating various contextual elements, such as user messages, agent information, and historical conversation data. This module fits into the overall architecture of the Lucy project by serving as a bridge between user interactions and AI model inputs, effectively solving the problem of generating coherent and contextually relevant prompts for AI-driven conversations.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Abstract Base Class (ABC)**: The `PromptBuilderInterface` defines a contract for prompt builders, ensuring that any concrete implementation adheres to a specific interface.
- **Dependency Injection**: The `PromptBuilder` class uses dependency injection to receive its dependencies (like `AgentManager`, `ConfigManager`, etc.), promoting loose coupling and easier testing.
- **Composition**: The `PromptBuilder` class composes various helper methods to handle specific tasks, such as resolving attachments and managing context.

The classes within the module are primarily related through composition and interface adherence. The `PromptBuilder` class implements the `PromptBuilderInterface`, ensuring that it provides the required functionality. There is no legacy/v2 split evident in the current implementation, indicating a focus on maintaining a single, cohesive design.

Important design decisions include:
- The use of logging for error handling and debugging, which is prevalent throughout the methods.
- The handling of context and historical data to enrich the prompts, which is crucial for maintaining conversational continuity.

## 3. Key Classes
| Class                     | Base/Parent                     | Purpose                                                                 |
|---------------------------|----------------------------------|-------------------------------------------------------------------------|
| `PromptBuilder`           | `PromptBuilderInterface`         | Constructs prompts for AI models, integrating various contextual elements. |
| `PromptBuilderInterface`  | `ABC`                            | Defines the interface for prompt builders, ensuring consistent implementation. |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                     |
|-------------------------------------------|---------------------------------------------------------|-------------------------------------|
| `src/prompt_builders/__init__.py`        | Initializes the module; no exports.                    | None                                |
| `src/prompt_builders/prompt_builder.py`  | Implements the `PromptBuilder` class and its methods.  | `PromptBuilder`                     |
| `src/prompt_builders/prompt_builder_interface.py` | Defines the `PromptBuilderInterface`.                   | `PromptBuilderInterface`            |

## 5. Dependencies
- **Standard library**:
  - `base64`
  - `glob`
  - `logging`
  - `os`
  - `datetime`
  - `pathlib`
  - `typing`
  
- **Third-party packages**:
  - `injector`
  
- **Internal modules**:
  - `src.config_manager`
  - `src.agent`
  - `src.storage.base`
  - `src.storage.interfaces`
  - `src.utils.document_context`
  - `src.utils.text_snippet_loader`
  - `src.chat2.facade`
  - `src.chat2.prompt_slice`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                             | Type   | Default                       | What it controls                                      |
|---------------------------------|--------|-------------------------------|------------------------------------------------------|
| `context_text_soft_max_tokens`  | int    | 2000                          | Maximum tokens for front-loaded context.             |
| `prompt_budget_max_tokens`      | int    | 12000                         | Maximum tokens for the entire prompt budget.         |
| `storage_root_path`             | str    | `/home/junwin/lucy_storage`  | Base path for storage.                               |
| `storage_namespace`              | str    | `data`                        | Namespace for storage.                               |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      |      | None        |

## 8. Module-Level Constants
| Constant                             | Value   |
|--------------------------------------|---------|
| `DEFAULT_PROMPT_BUDGET_TOKENS`      | 12000   |
| `PROMPT_BUDGET_SAFETY_MARGIN`       | 500     |
| `DIGEST_SCORE_THRESHOLD`             | 0.25    |
| `DOC_EMBEDDING_SCORE_THRESHOLD`      | 0.25    |
| `CONTEXT_TEXT_SOFT_MAX_TOKENS`      | 2000    |
| `DEFAULT_SEARCH_NAMESPACES`          | `["external"]` |

## 9. Methods (by class)

### `PromptBuilder`
| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, chat2_store: Optional[Chat2Store] = None, embedding_facade=None)` | Initializes the `PromptBuilder` with necessary dependencies. Accepts instances of `AgentManager`, `ConfigManager`, `Storage`, and optionally `Chat2Store` and `EmbeddingFacade`.                                                                                                                                                |
| `build_prompt`             | instance     | `def build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Constructs a full prompt for a model call, integrating various contextual elements. Logs the number of messages included and handles errors gracefully. Returns a list of message dictionaries. Key parameters include `content_text`, `conversation_id`, `agent_name`, and `account_name`. Returns a list of message dictionaries. |
| `_build_agent_system_message` | instance     | `def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str` | Combines system prompts, persona, and style prompts into a single system message. Returns the constructed message.                                                                                                                                                                                                                     |
| `_get_document_embedding_context` | instance     | `def _get_document_embedding_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]]` | Searches for relevant documents using semantic similarity based on the provided query. Returns a list of document contexts.                                                                                                                                                                                                            |
| `_get_digest_context`       | instance     | `def _get_digest_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]]` | Searches for relevant snippets across namespaces based on the provided query. Returns a list of digest contexts.                                                                                                                                                                                                                       |
| `_resolve_attachments`      | instance     | `def _resolve_attachments(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Resolves image and file IDs into a format suitable for the model. Handles both inline and marker modes for images. Returns a list of content parts.                                                                                                                                                                                      |
| `_build_images_dir`         | instance     | `def _build_images_dir(self) -> str`                                   | Returns the base directory path for images based on configuration settings.                                                                                                                                                                                                                                                                 |
| `_save_overflow_digest`     | instance     | `def _save_overflow_digest(self, *, account_name: str, conversation_id: str, new_snippet: str) -> Optional[str]` | Saves an overflow digest to a specified path, appending new snippets to existing content. Returns the full digest text or the new snippet if the file couldn't be written.                                                                                                                                                             |
| `_find_image_file`          | instance     | `def _find_image_file(self, images_dir: str, account_name: str, img_id: str) -> Optional[str]` | Finds an image file by its UUID in the account's images directory. Returns the first matching file path or None.                                                                                                                                                                                                                         |
| `_find_file`                | instance     | `def _find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str]` | Finds a general file by its UUID in the account's directory. Returns the file path or None.                                                                                                                                                                                                                                             |
| `_guess_mime_from_path`     | static       | `def _guess_mime_from_path(path: str) -> str`                          | Guesses the MIME type based on the file extension. Returns the MIME type as a string.                                                                                                                                                                                                                                                    |
| `_get_chat_history_messages` | instance     | `def _get_chat_history_messages(self, conversation_id: str, account_name: str, agent_name: str, max_conversations: int) -> List[Dict[str, str]]` | Retrieves chat history messages for a given conversation ID. Returns a list of message dictionaries.                                                                                                                                                                                                                                    |
| `_get_context_state`        | instance     | `def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]` | Returns the context object for a given context name. Handles errors gracefully and returns None if the context cannot be loaded.                                                                                                                                                                                                         |
| `_get_context_text`         | instance     | `def _get_context_text(self, account_name: str, context_name: str) -> str` | Renders the context text block for the LLM prompt. Returns the fully-resolved context text.                                                                                                                                                                                                                                             |
| `_ensure_current_query`     | instance     | `def _ensure_current_query(self, messages: List[Dict[str, Any]], current_query: str) -> List[Dict[str, Any]]` | Ensures that the current user query is appended to the messages list. Returns the updated messages list.                                                                                                                                                                                                                                 |
| `_summarize_overflow`       | instance     | `def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str` | Creates a digest from earlier message texts, concatenating excerpts until a character limit is reached. Returns the combined digest text.                                                                                                                                                                                               |

## 10. Usage Examples
```python
from src.prompt_builders.prompt_builder import PromptBuilder
from src.agent import AgentManager
from src.config_manager import ConfigManager
from src.storage.base import Storage

# Initialize dependencies
agent_manager = AgentManager()
config = ConfigManager()
storage = Storage()

# Create a PromptBuilder instance
prompt_builder = PromptBuilder(agent_manager, config, storage)

# Build a prompt
prompt = prompt_builder.build_prompt(
    content_text="What is the weather like today?",
    conversation_id="12345",
    agent_name="WeatherAgent",
    account_name="user_account"
)

print(prompt)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-soft approach, logging warnings instead of raising exceptions in many cases. This can lead to silent failures if not monitored.
- **Token Budgeting**: The prompt construction is sensitive to token limits, and exceeding these can lead to truncated contexts. Care should be taken to manage the size of inputs.
- **Legacy Compatibility**: Some methods, like `_get_chat_history_messages`, are kept for backward compatibility but are no longer used in the current flow, which may lead to confusion.
- **Thread Safety**: The module does not explicitly mention thread safety, so concurrent access to shared resources should be managed externally.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm | Unknown — further investigation needed.         |