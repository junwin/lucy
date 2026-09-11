```markdown
---
tags:
  - prompt_builders
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
---

## 1. Summary
The `prompt_builders` module provides a framework for constructing prompts in a conversational AI context. It integrates various memory retrieval systems, including episodic and semantic memories, to enhance the contextual relevance of generated prompts. The module addresses the challenge of managing and utilizing historical conversation data effectively, ensuring that prompts are both informative and concise.

## 2. Key Classes

| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| AttachmentResolver        | -                          | Resolves image/file IDs into content parts.                            |
| CoALAPromptBuilder        | PromptBuilder              | Integrates CoALA memory retrieval into prompt building.                |
| SemanticContextRetriever   | -                          | Retrieves semantic document context.                                    |
| DigestContextRetriever     | -                          | Retrieves archived digest context.                                      |
| HistorySelector           | -                          | Selects recent conversational events within a prompt history budget.   |
| PromptBuilder             | PromptBuilderInterface     | Orchestrates prompt building using various components.                 |
| PromptBuilderInterface     | ABC                        | Defines the interface for building prompts.                            |
| PromptSections            | -                          | Renders prompt sections without retrieval or budgeting.                 |
| TokenBudgetAllocator      | -                          | Manages token estimation and budget arithmetic.                        |

## 3. Source Files

| File                               | Responsibility                                         | Notable Exports                                      |
|------------------------------------|-------------------------------------------------------|-----------------------------------------------------|
| __init__.py                        | Initializes the module.                               | -                                                   |
| attachment_resolver.py             | Resolves attachments for prompts.                     | AttachmentResolver                                   |
| coala_prompt_builder.py            | Implements CoALA-based prompt building.               | CoALAPromptBuilder                                   |
| context_retrievers.py              | Retrieves context from semantic and digest memories.  | SemanticContextRetriever, DigestContextRetriever     |
| history_selector.py                | Manages selection of historical events.               | HistorySelector                                      |
| prompt_builder.py                  | Core prompt building logic.                           | PromptBuilder, estimate_tokens_from_text            |
| prompt_builder_interface.py         | Defines the prompt builder interface.                 | PromptBuilderInterface                                |
| prompt_sections.py                 | Manages sections of prompts.                          | PromptSections                                       |
| token_budget.py                    | Handles token budgeting for prompts.                  | TokenBudgetAllocator, DEFAULT_PROMPT_BUDGET_TOKENS |

## 4. Dependencies

- **Standard library**
  - os
  - logging
  - glob
  - base64
  - datetime
  - typing

- **Third-party packages**
  - injector
  
- **Internal modules**
  - src.config_manager
  - src.coala_memory.episodic
  - src.coala_memory.procedural
  - src.storage.base
  - src.storage.interfaces
  - src.utils.text_snippet_loader
  - src.agent
  - src.prompt_builders.prompt_builder_interface

## 5. Methods (by class)

### AttachmentResolver

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| resolve                    | instance      | `def resolve(self, account_name: str, image_ids: Optional[List[str]], file_ids: Optional[List[str]], agent_allowed_tools: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]:` | Resolves image and file IDs into content parts.                                               |
| build_images_dir           | instance      | `def build_images_dir(self) -> str:`                                   | Constructs the directory path for images based on configuration.                              |
| find_image_file            | staticmethod   | `@staticmethod def find_image_file(images_dir: str, account_name: str, img_id: str) -> Optional[str]:` | Finds an image file based on the provided ID.                                                |
| find_file                  | classmethod   | `@classmethod def find_file(cls, images_dir: str, account_name: str, file_id: str) -> Optional[str]:` | Finds a file based on the provided ID.                                                        |
| guess_mime_from_path      | staticmethod   | `@staticmethod def guess_mime_from_path(path: str) -> str:`           | Guesses the MIME type based on the file extension.                                           |

### CoALAPromptBuilder

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| build_prompt               | instance      | `def build_prompt(self, *args: Any, **kwargs: Any):`                   | Builds a prompt using CoALA memory retrieval.                                                 |
| _recall_current_episode     | instance      | `def _recall_current_episode(self, conversation_id: str, account_name: str, agent_name: str, max_events: int) -> Optional[EpisodicMemoryResult]:` | Recalls the current episodic memory for a conversation.                                       |
| _load_digest_contexts      | instance      | `def _load_digest_contexts(self, content_text: str, account_name: str, agent_name: str) -> List[Dict[str, Any]]:` | Loads digest contexts based on the content text.                                             |
| _get_context_state         | instance      | `def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]:` | Retrieves the context state for a given account and context name.                            |

### SemanticContextRetriever

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| retrieve                   | instance      | `def retrieve(self, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 9000, score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD) -> List[Dict[str, Any]]:` | Retrieves semantic document context based on a query.                                         |

### DigestContextRetriever

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| retrieve                   | instance      | `def retrieve(self, query: str, account_name: str, namespaces: Optional[List[str]] = None, top_k: int = 3, max_chars: int = 3000) -> List[Dict[str, Any]]:` | Retrieves archived digest context based on a query.                                           |

### HistorySelector

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| select                     | instance      | `def select(self, episodic_result: Optional[EpisodicMemoryResult], max_convs: int, history_budget: int, messages: List[Dict[str, Any]], account_name: str, conversation_id: str, agent_name: str, summarize_overflow: Callable[[List[str]], str], save_overflow_digest: Callable[..., Optional[str]]) -> Tuple[List[Dict[str, str]], str]:` | Selects historical events based on budget and maximum conversations.                           |

### PromptBuilder

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| build_prompt               | instance      | `def build_prompt(self, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None, image_ids: Optional[List[str]] = None, file_ids: Optional[List[str]] = None, supports_images: bool = True) -> List[Dict[str, Any]]:` | Constructs the full prompt message list.                                                      |
| _recall_current_episode     | instance      | `def _recall_current_episode(self, conversation_id: str, account_name: str, agent_name: str, max_events: int) -> Optional[EpisodicMemoryResult]:` | Recalls the current episodic memory for a conversation.                                       |
| _load_semantic_contexts    | instance      | `def _load_semantic_contexts(self, content_text: str, account_name: str, agent_name: str, agent: Optional[Agent], context_type: str, context_data: Dict[str, Any], use_embeddings: bool) -> List[Dict[str, Any]]:` | Loads semantic contexts based on the content text.                                           |

### TokenBudgetAllocator

| Method                     | Type          | Signature                                                                 | Description                                                                                     |
|----------------------------|---------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| allocate_history_budget    | instance      | `def allocate_history_budget(self, agent: Any, system_text_parts: Iterable[str], context_text: str, document_text: str, digest_text: str, user_text: str) -> PromptBudget:` | Allocates the budget for history based on various text components.                            |
| apply_context_soft_max     | instance      | `def apply_context_soft_max(self, context_text: str, agent: Any, account_name: str, context_name: str, agent_name: str) -> str:` | Applies a soft maximum to the context text based on token limits.                             |
```