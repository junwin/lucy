# Module Documentation for `src/curation`

## YAML Front Matter
```yaml
tags:
  - src_curation
  - lucyproject
  - CurationEngine
  - ChatEvent
  - LLMApi
  - EmbeddingFacade
  - EmbeddingStore
```

## 1. Summary
The `src.curation` module provides a comprehensive framework for managing chat session curation, including digest generation, archiving, and filtering operations. It serves as a core component of the larger architecture, facilitating the processing and summarization of chat events into structured formats. This module addresses the need for efficient session management, allowing users to distill conversations into meaningful summaries, archive original events, and apply filtering rules to curate content effectively.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Facade Pattern**: The `CurationEngine` class acts as a facade, encapsulating the complexity of various operations (summarization, archiving, filtering) and providing a unified interface.
- **Strategy Pattern**: Different modes of operation (filtering, summarizing, archiving) are implemented as strategies within the `CurationEngine`, allowing for flexible behavior based on user input.
- **Dependency Injection**: The use of `Chat2Store`, `LLMApi`, and other dependencies in the constructor of `CurationEngine` promotes loose coupling and enhances testability.

Classes within the module exhibit a composition relationship, where `CurationEngine` utilizes other classes like `summarizer`, `archiver`, and `resolver` to perform its tasks. The module does not appear to have a legacy/v2 split, indicating a cohesive design.

Key design decisions include the use of structured logging for error handling and the implementation of a fallback mechanism in the summarization process to ensure robustness.

## 3. Key Classes
| Class            | Base/Parent | Purpose                                                                 |
|------------------|-------------|-------------------------------------------------------------------------|
| CurationEngine    | None        | Orchestrates chat curation operations, including summarization and archiving. |
| ChatEvent         | None        | Represents individual chat events with associated metadata.             |
| LLMApi            | None        | Interface for interacting with the LLM for summarization tasks.        |
| EmbeddingFacade   | None        | Manages embedding operations for semantic search.                      |
| EmbeddingStore    | None        | Handles storage and retrieval of embedding records.                    |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                                                                 |
|-----------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`               | Initializes the curation module and exports key functions and classes. | CurationEngine, resolve_session, render_template, resolve_template, summarize_session, archive_session |
| `archiver.py`               | Handles archiving of chat sessions.                     | archive_session                                                                  |
| `core.py`                   | Main orchestration logic for curation operations.       | CurationEngine                                                                   |
| `resolver.py`               | Resolves sessions by ID or friendly name.               | resolve_session                                                                  |
| `summarizer.py`             | Summarizes chat events into structured digests.         | summarize_session                                                                |
| `templates.py`              | Manages template rendering for digests.                  | render_template, resolve_template                                                |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `datetime`
  - `pathlib`
  - `typing`
  
- **Third-party packages**:
  - `galet` (for LLM interaction)
  
- **Internal modules**:
  - `src.chat2.facade`
  - `src.chat2.models`
  - `src.embeddings.facade`
  - `src.storage.interfaces`
  - `src.storage.models`
  
- **Optional dependencies**:
  - None identified.

## 6. Configuration / Settings
| Key                     | Type    | Default                     | What it controls                                      |
|-------------------------|---------|-----------------------------|------------------------------------------------------|
| None                    | None    | None                        | None                                                 |

## 7. Exceptions
| Exception               | Base    | When Raised                                      |
|-------------------------|---------|--------------------------------------------------|
| None                    | None    | None                                             |

## 8. Module-Level Constants
| Constant                | Value    | Description                                      |
|-------------------------|----------|--------------------------------------------------|
| SUMMARIZE_SYSTEM_PROMPT | String   | System prompt for LLM summarization.             |

## 9. Methods (by class)

### CurationEngine
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`              | Instance    | `def __init__(self, chat2_store: Chat2Store, llm_api: LLMApi, ...)`   | Initializes the CurationEngine with necessary dependencies. Key parameters include `chat2_store`, `llm_api`, and paths for digests and archives.                                                                 |
| `curate`                | Instance    | `def curate(self, session_id: Optional[str] = None, ...)`              | Runs curation on a session based on the specified mode (filter, summarize, archive). Returns a dictionary with the status and results. Key parameters include `session_id`, `account`, and `mode`.         |
| `_mode_filter`          | Instance    | `def _mode_filter(self, sid: str, events: List[ChatEvent], ...)`       | Applies rule-based filtering to the events. Returns a summary of the filtering process. Key parameters include `sid`, `events`, and `rules`.                                                              |
| `_mode_summarize`      | Instance    | `def _mode_summarize(self, sid: str, events: List[ChatEvent], ...)`   | Generates a digest using LLM summarization. Returns a dictionary with the status and generated note text. Key parameters include `sid`, `events`, and `template_name`.                                     |
| `_mode_archive`        | Instance    | `def _mode_archive(self, sid: str, events: List[ChatEvent], ...)`     | Summarizes, archives original events, and replaces them with a digest. Returns a dictionary with the status and note text. Key parameters include `sid`, `events`, and `template_name`.                   |
| `_write_digest`         | Instance    | `def _write_digest(self, session_id: str, account: str, note_text: str)` | Writes the generated digest to a file. Returns the output path of the written digest.                                                                                                                      |
| `_maybe_embed_digest`   | Instance    | `def _maybe_embed_digest(self, note_text: str, note_path: Path, ...)`  | Embeds the digest text for semantic search if embedding dependencies are available.                                                                                                                         |

### ChatEvent
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Represents individual chat events with associated metadata.                                                                                                                                               |

### LLMApi
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Interface for interacting with the LLM for summarization tasks.                                                                                                                                          |

### EmbeddingFacade
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Manages embedding operations for semantic search.                                                                                                                                                          |

### EmbeddingStore
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Handles storage and retrieval of embedding records.                                                                                                                                                        |

## 10. Usage Examples
```python
from src.curation import CurationEngine

# Initialize dependencies
chat2_store = Chat2Store()
llm_api = LLMApi()

# Create a CurationEngine instance
curation_engine = CurationEngine(chat2_store=chat2_store, llm_api=llm_api)

# Run curation on a session
result = curation_engine.curate(session_id="12345", account="user_account", mode="summarize", publish=True)
print(result)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs structured logging to capture errors, particularly in the LLM interaction and file I/O operations. It uses fallback mechanisms to ensure that even if the LLM fails, a basic digest can still be generated.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources like `Chat2Store`.
- **Known Limitations**: The summarization process is limited by the maximum character count for LLM input, which is set to 32,000 characters. If the events exceed this limit, they will be truncated.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|--------------------------------------------------|
| Unknown                 | Unknown — trace imports to confirm.              |