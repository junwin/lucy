# Module Documentation for `src/prompt_builders`

## YAML Front Matter
```yaml
tags:
  - src_prompt_builders
  - lucyproject
  - AttachmentResolver
  - CoALAPromptBuilder
  - SemanticContextRetriever
  - DigestContextRetriever
  - HistorySelector
  - PromptBuilder
  - PromptBuilderInterface
  - PromptSections
  - TokenBudgetAllocator
```

## 1. Summary
The `src/prompt_builders` module is responsible for constructing prompts for conversational agents by integrating various memory retrieval systems and context management strategies. It orchestrates the interaction between different components, such as semantic and episodic memory, to generate coherent and contextually relevant prompts. This module fits into the overall architecture of the Lucy project, which aims to enhance conversational AI capabilities by providing a structured way to manage and utilize historical interactions and contextual information. The primary problem it solves is the effective generation of prompts that leverage past conversations and relevant documents, ensuring that the agent can provide informed and contextually appropriate responses.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Dependency Injection**: Utilizes the `injector` library to manage dependencies, particularly for the `PromptBuilder` class, which requires various services like `AgentManager`, `ConfigManager`, and memory systems.
- **Composition**: The `PromptBuilder` class composes multiple components such as `AttachmentResolver`, `SemanticContextRetriever`, and `DigestContextRetriever` to build prompts.
- **Abstract Base Class (ABC)**: The `PromptBuilderInterface` defines a contract for prompt builders, ensuring that any implementation adheres to a consistent interface.

Classes within the module relate through composition and inheritance. For instance, `CoALAPromptBuilder` extends `PromptBuilder`, adding specific memory retrieval logic. The module does not appear to have a legacy/v2 split, indicating a unified design approach.

Key design decisions include the use of logging for error handling and the careful management of token budgets to ensure that prompts do not exceed predefined limits, which is crucial for maintaining performance and relevance in conversational contexts.

## 3. Key Classes
| Class                      | Base/Parent                | Purpose                                                                 |
|----------------------------|----------------------------|-------------------------------------------------------------------------|
| AttachmentResolver          | N/A                        | Resolves image/file IDs into content parts for prompts.                 |
| CoALAPromptBuilder          | PromptBuilder              | Builds prompts with memory retrieval routed through CoALA.              |
| SemanticContextRetriever     | N/A                        | Retrieves semantic document context through CoALA.                      |
| DigestContextRetriever       | N/A                        | Retrieves archived digest context through a legacy embedding seam.      |
| HistorySelector             | N/A                        | Selects recent conversational events within the prompt history budget.  |
| PromptBuilder               | PromptBuilderInterface     | Orchestrates prompt building using various components.                  |
| PromptBuilderInterface      | ABC                        | Defines the interface for prompt builders.                               |
| PromptSections              | N/A                        | Renders provider-neutral prompt sections without retrieval or budgeting. |
| TokenBudgetAllocator        | N/A                        | Manages token estimation and budget arithmetic for prompts.             |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                             | Initializes the module.                                 | None                                                                            |
| `attachment_resolver.py`                  | Resolves attachments for prompts.                       | `AttachmentResolver`                                                            |
| `coala_prompt_builder.py`                 | Builds prompts with CoALA memory retrieval.            | `CoALAPromptBuilder`                                                            |
| `context_retrievers.py`                   | Retrieves context from semantic and digest memories.    | `SemanticContextRetriever`, `DigestContextRetriever`                           |
| `history_selector.py`                     | Selects relevant history events for prompts.           | `HistorySelector`                                                               |
| `prompt_builder.py`                       | Main prompt building logic.                             | `PromptBuilder`, `estimate_tokens_from_text`, `DEFAULT_PROMPT_BUDGET_TOKENS`, `PROMPT_BUDGET_SAFETY_MARGIN`, `CONTEXT_TEXT_SOFT_MAX_TOKENS`, `DIGEST_SCORE_THRESHOLD`, `DIGEST_SEARCH_NAMESPACES`, `DOC_EMBEDDING_SCORE_THRESHOLD`, `DEFAULT_SEARCH_NAMESPACES`, `CONVERSATION_EVENT_KINDS` |
| `prompt_builder_interface.py`             | Defines the interface for prompt builders.              | `PromptBuilderInterface`                                                       |
| `prompt_sections.py`                      | Manages sections of prompts.                            | `PromptSections`                                                                |
| `token_budget.py`                         | Manages token budgeting for prompts.                   | `TokenBudgetAllocator`                                                          |

## 5. Dependencies
- **Standard library**:
  - `logging`
  - `os`
  - `glob`
  - `pathlib`
  - `datetime`
  - `abc`
  - `dataclasses`
  - `typing`
  
- **Third-party packages**:
  - `injector`
  
- **Internal modules**:
  - `src.config_manager`
  - `src.agent`
  - `src.coala_memory.episodic`
  - `src.coala_memory.procedural`
  - `src.storage.base`
  - `src.storage.interfaces`
  - `src.utils.text_snippet_loader`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                          | Type   | Default                          | What it controls                                      |
|------------------------------|--------|----------------------------------|------------------------------------------------------|
| `storage_root_path`          | str    | `/home/junwin/lucy_storage`     | Base path for storage of images and files.          |
| `storage_namespace`           | str    | `data`                           | Namespace for organizing stored data.                |

## 7. Exceptions
| Exception         | Base         | When Raised                                      |
|-------------------|--------------|-------------------------------------------------|
| None              | N/A          | None                                            |

## 8. Module-Level Constants
| Constant                             | Value         |
|--------------------------------------|---------------|
| `DEFAULT_PROMPT_BUDGET_TOKENS`      | 12000         |
| `PROMPT_BUDGET_SAFETY_MARGIN`       | 500           |
| `CONTEXT_TEXT_SOFT_MAX_TOKENS`      | 2000          |
| `DIGEST_SCORE_THRESHOLD`             | 0.25          |
| `DOC_EMBEDDING_SCORE_THRESHOLD`      | 0.25          |
| `DIGEST_SEARCH_NAMESPACES`           | `["digests"]` |
| `DEFAULT_SEARCH_NAMESPACES`          | `["external"]`|
| `CONVERSATION_EVENT_KINDS`           | `["user_message", "assistant_message"]` |

## 9. Methods (by class)

### AttachmentResolver
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, config: ConfigManager) -> None`                    | Initializes the resolver with a configuration manager.                     |
| `resolve`                  | instance     | `def resolve(self, *, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Resolves image and file IDs into content parts for prompts.                |
| `build_images_dir`        | instance     | `def build_images_dir(self) -> str`                                     | Constructs the directory path for images based on configuration.           |
| `find_image_file`         | static       | `def find_image_file(images_dir: str, account_name: str, img_id: str) -> Optional[str]` | Finds an image file based on the provided parameters.                      |
| `find_file`               | class        | `def find_file(cls, images_dir: str, account_name: str, file_id: str) -> Optional[str]` | Finds a file based on the provided parameters.                             |
| `guess_mime_from_path`    | static       | `def guess_mime_from_path(path: str) -> str`                           | Guesses the MIME type based on the file extension.                        |

### CoALAPromptBuilder
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, *args: Any, procedural_memory: Optional[ProceduralMemory] = None, **kwargs: Any) -> None` | Initializes the prompt builder with optional procedural memory.            |
| `build_prompt`             | instance     | `def build_prompt(self, *args: Any, **kwargs: Any)`                     | Builds the prompt, resetting the procedural cache and current query.       |
| `_recall_current_episode`   | instance     | `def _recall_current_episode(self, *, conversation_id: str, account_name: str, agent_name: str, max_events: int) -> Optional[EpisodicMemoryResult]` | Recalls the current episode from episodic memory.                          |
| `_load_digest_contexts`    | instance     | `def _load_digest_contexts(self, *, content_text: str, account_name: str, agent_name: str) -> List[Dict[str, Any]]` | Loads digest contexts based on the provided parameters.                    |
| `_get_context_state`       | instance     | `def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]` | Retrieves the context state for the specified account and context name.    |

### SemanticContextRetriever
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, semantic_memory: Optional[SemanticMemory]) -> None` | Initializes the retriever with optional semantic memory.                   |
| `retrieve`                 | instance     | `def retrieve(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]]` | Retrieves semantic document context based on the query and parameters.     |

### DigestContextRetriever
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, *, storage: Storage, embedding_facade: Any = None, embedding_store: Optional[EmbeddingStore] = None) -> None` | Initializes the retriever with storage and optional embedding components.   |
| `retrieve`                 | instance     | `def retrieve(self, *, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]]` | Retrieves archived digest context based on the query and parameters.       |

### HistorySelector
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `event_content`            | static       | `def event_content(event: Any) -> str`                                  | Extracts content from an event.                                            |
| `select`                   | instance     | `def select(self, *, episodic_result: Optional[EpisodicMemoryResult], max_convs: int, history_budget: int, messages: List[Dict[str, Any]], account_name: str, conversation_id: str, agent_name: str, summarize_overflow: Callable[[List[str]], str], save_overflow_digest: Callable[..., Optional[str]]) -> Tuple[List[Dict[str, str]], str]` | Selects events from the episodic result based on the budget and max conversations. |
| `summarize_overflow`       | static       | `def summarize_overflow(texts: List[str], max_chars: int = 800) -> str` | Summarizes overflow messages into a single string.                        |

### PromptBuilder
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, embedding_facade=None, embedding_store: Optional[EmbeddingStore] = None, semantic_memory=None, episodic_memory: Optional[EpisodicMemory] = None) -> None` | Initializes the prompt builder with various dependencies.                  |
| `build_prompt`             | instance     | `def build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]` | Builds the full prompt message list.                                      |
| `_append_session_info`     | instance     | `def _append_session_info(self, **kwargs: Any) -> None`                 | Appends session information to the messages.                              |
| `_apply_context_soft_max`   | instance     | `def _apply_context_soft_max(self, *, context_text: str, agent: Optional[Agent], account_name: str, context_name: str, agent_name: str) -> str` | Applies soft max limits to the context text.                             |
| `_get_context_data`        | instance     | `def _get_context_data(self, *, account_name: str, context_name: str) -> Dict[str, Any]` | Retrieves context data based on account and context name.                 |

### PromptBuilderInterface
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `build_prompt`             | abstract     | `def build_prompt(self, *, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[ChatMessageDict]` | Abstract method to build a prompt.                                         |

### PromptSections
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `append_session_info`      | static       | `def append_session_info(*, messages: List[Dict[str, Any]], system_text_parts: List[str], episodic_result: Optional[EpisodicMemoryResult], conversation_id: str, agent_name: str) -> None` | Appends session information to the messages.                              |
| `append_document_contexts` | static       | `def append_document_contexts(messages: List[Dict[str, Any]], doc_contexts: List[Dict[str, Any]]) -> None` | Appends document contexts to the messages.                                 |
| `append_digest_contexts`   | static       | `def append_digest_contexts(messages: List[Dict[str, Any]], digest_contexts: List[Dict[str, Any]]) -> None` | Appends digest contexts to the messages.                                   |
| `build_agent_system_message`| static      | `def build_agent_system_message(agent_name: str, agent: Optional[Agent]) -> str` | Builds a system message for the agent.                                    |
| `context_text`             | static       | `def context_text(ctx: Optional[Any]) -> str`                           | Generates context text from the provided context.                         |

### TokenBudgetAllocator
| Method                     | Type         | Signature                                                                 | Description                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, config: ConfigManager) -> None`                     | Initializes the allocator with a configuration manager.                    |
| `allocate_history_budget`   | instance     | `def allocate_history_budget(self, *, agent: Any, system_text_parts: Iterable[str], context_text: str, document_text: str, digest_text: str, user_text: str) -> PromptBudget` | Allocates a budget for history based on various text components.          |
| `apply_context_soft_max`   | instance     | `def apply_context_soft_max(self, *, context_text: str, agent: Any, account_name: str, context_name: str, agent_name: str) -> str` | Applies soft max limits to the context text.                             |
| `build_breakdown`          | static       | `def build_breakdown(*, budget: PromptBudget, history_messages: Iterable[Mapping[str, Any]], overflow_digest_text: str) -> Dict[str, int]` | Builds a breakdown of token usage based on the budget and messages.      |

## 10. Usage Examples
```python
from src.prompt_builders import PromptBuilder
from src.config_manager import ConfigManager
from src.agent import AgentManager
from src.storage.base import Storage

# Initialize dependencies
config = ConfigManager()
agent_manager = AgentManager()
storage = Storage()

# Create a PromptBuilder instance
prompt_builder = PromptBuilder(agent_manager, config, storage)

# Build a prompt
messages = prompt_builder.build_prompt(
    content_text="What is the weather today?",
    conversation_id="12345",
    agent_name="WeatherBot",
    account_name="user_account"
)

print(messages)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs logging to capture exceptions, particularly in methods that involve file I/O and memory retrieval. This ensures that failures do not crash the application but are logged for debugging.
- **Token Budgeting**: The token budget management is crucial; exceeding limits can lead to truncated prompts. Careful attention is needed when constructing prompts to ensure they remain within budget.
- **Context Management**: The context retrieval methods may return empty results if the specified context does not exist or if the memory systems are not properly initialized.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| `src.agent`                  | Uses `PromptBuilder` for generating prompts.     |
| `src.coala_memory`           | Integrates with `CoALAPromptBuilder` for memory.|
| `src.storage`                | Utilizes `PromptBuilder` for context retrieval.  |
| `src.utils`                  | Uses `TokenBudgetAllocator` for token management.|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |