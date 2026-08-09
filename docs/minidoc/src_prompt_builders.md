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
The `src/prompt_builders` module is responsible for constructing prompts for AI models, particularly in the context of conversational agents. It integrates various components such as agent management, context retrieval, and document embedding to create comprehensive prompts that include user messages, system messages, and relevant contextual information. This module fits into the overall architecture of the Lucy project by serving as a bridge between user interactions and the AI model, ensuring that the model receives well-structured and contextually rich inputs. The primary problem it solves is the effective generation of prompts that maximize the utility of the AI model while managing token budgets and contextual relevance.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Abstract Base Class (ABC)**: The `PromptBuilderInterface` defines a contract for prompt builders, ensuring that any implementation adheres to a specific interface.
- **Dependency Injection**: The `PromptBuilder` class uses dependency injection to receive its dependencies (e.g., `AgentManager`, `ConfigManager`, `Storage`, etc.), promoting loose coupling and easier testing.
- **Composition**: The `PromptBuilder` class composes various helper methods to handle specific tasks like context retrieval and message assembly.

The classes within the module are closely related, with `PromptBuilder` implementing the `PromptBuilderInterface`. The design decisions emphasize flexibility and extensibility, allowing for easy integration of new features or modifications to existing behavior.

## 3. Key Classes
| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| `PromptBuilder`           | `PromptBuilderInterface`    | Constructs prompts for AI models, integrating various contextual elements. |
| `PromptBuilderInterface`  | `ABC`                      | Defines the interface for prompt builders, ensuring consistent implementation. |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                     |
|-------------------------------------------|---------------------------------------------------------|-------------------------------------|
| `__init__.py`                             | Initializes the module; no exports.                    | None                                |
| `prompt_builder.py`                       | Implements the `PromptBuilder` class and its methods.  | `PromptBuilder`                     |
| `prompt_builder_interface.py`             | Defines the `PromptBuilderInterface`.                   | `PromptBuilderInterface`            |

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
  - `src.utils.text_snippet_loader`
  - `src.chat2.facade`
  - `src.chat2.prompt_slice`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                                      | Type   | Default | What it controls                                      |
|------------------------------------------|--------|---------|------------------------------------------------------|
| `PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS` | int    | 2000    | Maximum tokens for front-loaded context.             |
| `PROMPT_BUDGET_MAX_TOKENS`              | int    | 12000   | Maximum tokens for the entire prompt budget.         |
| `storage_root_path`                      | str    | `/home/junwin/lucy_storage` | Base path for storage.                               |
| `storage_namespace`                      | str    | `data`  | Namespace for storage.                               |

## 7. Exceptions
| Exception                | Base                | When Raised                                      |
|--------------------------|---------------------|--------------------------------------------------|
| None                     | None                | None                                             |

## 8. Module-Level Constants
| Constant                                   | Value   |
|--------------------------------------------|---------|
| `DEFAULT_PROMPT_BUDGET_TOKENS`            | 12000   |
| `PROMPT_BUDGET_SAFETY_MARGIN`             | 500     |
| `DEFAULT_SOURCE_BUDGETS`                   | `{"agent": 0.4, "account": 0.4, "context": 0.2}` |
| `DIGEST_SCORE_THRESHOLD`                   | 0.25    |
| `DOC_EMBEDDING_SCORE_THRESHOLD`           | 0.25    |
| `CONTEXT_TEXT_SOFT_MAX_TOKENS`            | 2000    |

## 9. Methods (by class)

### `PromptBuilder`
| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                | Instance     | `def __init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, chat2_store: Optional[Chat2Store] = None, embedding_facade=None)` | Initializes the `PromptBuilder` with necessary dependencies.                                                                                                                                                                                                                                                                               |
| `build_prompt`            | Instance     | `def build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Constructs a prompt for the AI model, integrating user messages, system messages, and contextual information. Key parameters include `content_text` (the user's message), `conversation_id` (to track the session), and `agent_name` (to identify the agent). Returns a list of message dictionaries formatted for the model. |
| `_build_agent_system_message` | Instance     | `def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str` | Constructs the system message for the agent, combining various prompts and styles. Returns a formatted string.                                                                                                                                                                                                                          |
| `_get_document_embedding_context` | Instance     | `def _get_document_embedding_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]]` | Retrieves relevant documents based on semantic similarity to the user's query. Returns a list of document contexts.                                                                                                                                                                                                                     |
| `_get_digest_context`    | Instance     | `def _get_digest_context(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]]` | Searches for relevant snippets across namespaces based on the user's query. Returns a list of digest contexts.                                                                                                                                                                                                                          |
| `_resolve_attachments`    | Instance     | `def _resolve_attachments(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Resolves image and file IDs into a format suitable for the model, handling both inline and marker modes. Returns a list of content parts.                                                                                                                                                                                                 |
| `_get_chat_history_messages` | Instance     | `def _get_chat_history_messages(self, conversation_id: str, account_name: str, agent_name: str, max_conversations: int) -> List[Dict[str, str]]` | Retrieves chat history messages for a given conversation ID, returning a list of message dictionaries.                                                                                                                                                                                                                                   |
| `_get_context_state`     | Instance     | `def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]` | Retrieves the context state for a given account and context name. Returns the context state object or None.                                                                                                                                                                                                                              |
| `_get_context_text`      | Instance     | `def _get_context_text(self, account_name: str, context_name: str) -> str` | Loads context text from storage, including any imported skills. Returns the context text as a string.                                                                                                                                                                                                                                   |
| `_ensure_current_query`   | Instance     | `def _ensure_current_query(self, messages: List[Dict[str, Any]], current_query: str) -> List[Dict[str, Any]]` | Ensures the current user query is included in the message list, avoiding duplicates. Returns the updated message list.                                                                                                                                                                                                                   |
| `_get_context_soft_max_tokens` | Instance     | `def _get_context_soft_max_tokens(self) -> int` | Resolves the soft max tokens for front-loaded context based on environment variables, config, or defaults. Returns an integer.                                                                                                                                                                                                            |
| `_summarize_overflow`    | Instance     | `def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str` | Creates a digest from earlier messages, concatenating excerpts until a character limit is reached. Returns a formatted string.                                                                                                                                                                                                            |

## 10. Usage Examples
```python
from src.prompt_builders.prompt_builder import PromptBuilder

# Assuming dependencies are already instantiated
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
- **Error Handling**: The module employs a fail-soft approach for context and document retrieval, logging warnings instead of raising exceptions. This ensures that the prompt generation can continue even if some context is unavailable.
- **Token Budgeting**: The module carefully manages token budgets, logging warnings if the context exceeds soft max limits. Users should be aware of the implications of exceeding these limits on prompt effectiveness.
- **Backward Compatibility**: The `_get_chat_history_messages` method is retained for backward compatibility but is no longer used in the current token-based flow.
- **Thread Safety**: The module does not explicitly mention thread safety, so concurrent access to shared resources should be managed externally.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|---------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — further investigation needed. |