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
The `src.curation` module provides a comprehensive framework for managing chat session curation, including digest generation, archiving, and filtering operations. It serves as a core component of the larger architecture, facilitating the processing and summarization of chat events into structured formats. This module addresses the need for efficient session management, allowing users to distill conversations into meaningful summaries, archive original events, and apply filtering rules to enhance the quality of the data retained.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Facade Pattern**: The `CurationEngine` class acts as a facade, encapsulating the complexity of various operations (summarization, archiving, filtering) and providing a unified interface for users.
- **Strategy Pattern**: Different modes of operation (filter, summarize, archive) are implemented as strategies within the `curate` method, allowing for flexible behavior based on user input.
- **Dependency Injection**: The use of `Chat2Store`, `LLMApi`, and other dependencies in the `CurationEngine` constructor exemplifies dependency injection, promoting loose coupling and easier testing.

Classes within the module are primarily composed, with `CurationEngine` orchestrating interactions between various components like the resolver, summarizer, and archiver. There is no explicit legacy/v2 split, but the design choices reflect a focus on modularity and extensibility.

Key design decisions include the use of structured Markdown for digests, which enhances readability and usability, and the implementation of robust logging for error handling and operational transparency.

## 3. Key Classes
| Class            | Base/Parent | Purpose                                                                 |
|------------------|-------------|-------------------------------------------------------------------------|
| CurationEngine    | None        | Orchestrates chat curation operations, including summarization and archiving. |
| ChatEvent         | None        | Represents individual chat events, encapsulating their properties and behaviors. |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                                      |
|-----------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`               | Initializes the curation module and exports key functions and classes. | CurationEngine, resolve_session, render_template, resolve_template, summarize_session, archive_session |
| `archiver.py`               | Handles archiving of chat sessions and event management. | archive_session                                      |
| `core.py`                   | Contains the main orchestration logic for curation.    | CurationEngine                                       |
| `resolver.py`               | Resolves chat sessions by ID or friendly name.         | resolve_session                                      |
| `summarizer.py`             | Provides LLM-based summarization for chat sessions.     | summarize_session                                     |
| `templates.py`              | Manages template rendering for digests.                 | render_template, resolve_template                    |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `datetime`
  - `pathlib`
  - `typing`
  
- **Third-party packages**:
  - `galet` (for LLM API interaction)
  
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
|-------------------------|---------|-------------------------------------------------|
| None                    | None    | None                                            |

## 8. Module-Level Constants
| Constant                | Value    | Description                                      |
|-------------------------|----------|--------------------------------------------------|
| SUMMARIZE_SYSTEM_PROMPT | String   | System prompt for LLM summarization.             |

## 9. Methods (by class)

### CurationEngine
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`              | Instance    | `def __init__(self, chat2_store: Chat2Store, llm_api: LLMApi, ...)`    | Initializes the CurationEngine with necessary dependencies.                                                                                                                                              |
| `curate`                | Instance    | `def curate(self, session_id: Optional[str] = None, ...)`               | Runs curation on a session, allowing for filtering, summarization, or archiving based on the specified mode. Returns a dictionary with the result status and relevant data.                             |
| `_mode_filter`          | Instance    | `def _mode_filter(self, sid: str, events: List[ChatEvent], ...)`        | Applies filtering rules to the session events, modifying the session in the store. Returns a summary of the filtering operation.                                                                          |
| `_mode_summarize`      | Instance    | `def _mode_summarize(self, sid: str, events: List[ChatEvent], ...)`    | Generates a digest of the session events using an LLM, optionally writing it to disk. Returns a dictionary with the status and generated note text.                                                       |
| `_mode_archive`        | Instance    | `def _mode_archive(self, sid: str, events: List[ChatEvent], ...)`      | Summarizes, archives original events, and replaces them with a digest. Returns a dictionary with the status of the archiving operation.                                                                  |
| `_write_digest`         | Instance    | `def _write_digest(self, session_id: str, account: str, note_text: str)`| Writes the generated digest to a specified path, creating necessary directories. Returns the path to the written digest.                                                                                 |
| `_maybe_embed_digest`   | Instance    | `def _maybe_embed_digest(self, note_text: str, note_path: Path, ...)`  | Embeds the digest text for semantic search if embedding dependencies are available. Handles potential errors gracefully.                                                                                 |

### ChatEvent
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Represents individual chat events, encapsulating their properties and behaviors.                                                                                                                          |

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
- **Error Handling**: The module employs logging to capture warnings and exceptions, particularly in the `resolve_session` and `archive_session` functions, ensuring that issues are logged without crashing the application.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources like `Chat2Store`.
- **LLM Limitations**: The summarization relies on the LLM's ability to generate meaningful output. If the LLM fails, a fallback digest is generated, but this may not capture the full context.
- **File I/O**: The archiving process involves file operations that may fail due to permissions or disk space issues, which are handled with logging.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|---------------------------------------------------|
| Unknown                 | Unknown — trace imports to confirm.               |