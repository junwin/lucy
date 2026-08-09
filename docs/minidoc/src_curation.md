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
  - ChatSessionMeta
```

## 1. Summary
The `src.curation` module provides a comprehensive framework for managing chat session curation, including digest generation, archiving, and filtering operations. It serves as a core component of the larger architecture, facilitating the processing and summarization of chat events into structured formats. This module addresses the need for efficient session management, allowing users to distill conversations into meaningful summaries, archive original events, and apply filtering rules to enhance the quality of stored data.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Facade Pattern**: The `CurationEngine` class acts as a facade, wrapping various functionalities (resolver, summarizer, archiver, and template renderer) into a single interface.
- **Strategy Pattern**: Different modes of operation (filtering, summarizing, archiving) are implemented as strategies within the `curate` method of `CurationEngine`.
- **Dependency Injection**: The use of external services like `Chat2Store`, `LLMApi`, and `EmbeddingFacade` is facilitated through constructor injection, promoting loose coupling.

Classes within the module exhibit a composition relationship, where `CurationEngine` utilizes other classes to perform its tasks. The module does not appear to have a legacy/v2 split, indicating a cohesive design. Important design decisions are reflected in the extensive use of logging for error handling and operational transparency.

## 3. Key Classes
| Class            | Base/Parent | Purpose                                                                 |
|------------------|-------------|-------------------------------------------------------------------------|
| CurationEngine    | None        | Orchestrates chat curation operations, including filtering, summarizing, and archiving. |
| ChatEvent         | None        | Represents individual chat events, encapsulating their properties and behaviors. |
| LLMApi            | None        | Interface for interacting with the LLM for summarization tasks.        |
| EmbeddingFacade   | None        | Manages embedding operations for semantic search.                      |
| ChatSessionMeta   | None        | Metadata structure for chat sessions, used in session resolution.      |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                                      |
|-----------------------------|---------------------------------------------------------|-----------------------------------------------------|
| `__init__.py`              | Initializes the curation module and exports key functions and classes. | CurationEngine, resolve_session, render_template, resolve_template, summarize_session, archive_session |
| `archiver.py`              | Handles archiving of chat sessions and replacing events with digests. | archive_session                                      |
| `core.py`                  | Contains the CurationEngine class for orchestrating curation tasks. | CurationEngine                                       |
| `resolver.py`              | Resolves chat sessions by friendly name or session ID. | resolve_session                                      |
| `summarizer.py`            | Provides LLM-based summarization for chat sessions.   | summarize_session                                    |
| `templates.py`             | Manages template rendering for curation digests.      | render_template, resolve_template                   |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `datetime`
  - `pathlib`
  - `typing`
  
- **Third-party packages**:
  - None identified.

- **Internal modules**:
  - `src.chat2.facade`
  - `src.chat2.models`
  - `src.embeddings.facade`
  - `src.llm.interface`
  - `src.storage.models`

- **Optional dependencies**:
  - None identified.

## 6. Configuration / Settings
| Key                     | Type    | Default                     | What it controls                                      |
|-------------------------|---------|-----------------------------|------------------------------------------------------|
| None                    | None    | None                        | None                                                 |

## 7. Exceptions
| Exception               | Base    | When Raised                                         |
|-------------------------|---------|----------------------------------------------------|
| None                    | None    | None                                               |

## 8. Module-Level Constants
| Constant                | Value    | Description                                           |
|-------------------------|----------|-------------------------------------------------------|
| SUMMARIZE_SYSTEM_PROMPT | String   | System prompt for LLM summarization.                  |

## 9. Methods (by class)

### CurationEngine
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`             | Instance    | `def __init__(self, chat2_store: Chat2Store, llm_api: LLMApi, ...)`    | Initializes the CurationEngine with necessary dependencies. Key parameters include `chat2_store`, `llm_api`, and optional paths for digests and archives.                                                                                     |
| `curate`               | Instance    | `def curate(self, session_id: Optional[str] = None, ...)`               | Runs curation on a session, allowing for filtering, summarizing, or archiving. Returns a dictionary with status and results. Key parameters include `session_id`, `account`, `mode`, and `publish`.                                                      |
| `_mode_filter`         | Instance    | `def _mode_filter(self, sid: str, events: List[ChatEvent], ...)`       | Applies rule-based filtering to the events of a session. Returns a summary of the filtering operation. Key parameters include `sid`, `events`, and `rules`.                                                                                          |
| `_mode_summarize`      | Instance    | `def _mode_summarize(self, sid: str, events: List[ChatEvent], ...)`    | Generates a digest using LLM summarization. Returns a dictionary with the digest and status. Key parameters include `sid`, `events`, `template_name`, and `publish`.                                                                                     |
| `_mode_archive`        | Instance    | `def _mode_archive(self, sid: str, events: List[ChatEvent], ...)`      | Summarizes, archives original events, and replaces them with a digest. Returns a dictionary with status and output path. Key parameters include `sid`, `events`, `template_name`, and `publish`.                                                          |
| `_write_digest`        | Instance    | `def _write_digest(self, session_id: str, account: str, note_text: str)` | Writes the generated digest to a file. Returns the output path. Key parameters include `session_id`, `account`, and `note_text`.                                                                                                                        |
| `_maybe_embed_digest`  | Instance    | `def _maybe_embed_digest(self, note_text: str, note_path: Path, ...)`  | Embeds the digest for semantic search if embedding dependencies are available. Key parameters include `note_text`, `note_path`, `session_id`, and `account`.                                                                                             |

### ChatEvent
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Represents individual chat events, encapsulating their properties and behaviors.                                                                                                                         |

### LLMApi
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Interface for interacting with the LLM for summarization tasks.                                                                                                                                          |

### EmbeddingFacade
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Manages embedding operations for semantic search.                                                                                                                                                         |

### ChatSessionMeta
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Metadata structure for chat sessions, used in session resolution.                                                                                                                                       |

## 10. Usage Examples
```python
from src.curation import CurationEngine
from src.chat2.facade import Chat2Store
from src.llm.interface import LLMApi

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
- **Error Handling**: The module employs a fail-fast approach, logging warnings and errors when sessions are not found or when LLM calls fail.
- **Backward Compatibility**: The design does not indicate any legacy support, suggesting a focus on current functionality.
- **Thread-Safety**: The module does not explicitly mention thread-safety, which may be a concern if multiple instances of `CurationEngine` are used concurrently.
- **Known Limitations**: The summarization relies on the LLM's capabilities, which may vary based on the model used and the input data.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|---------------------------------------------------|
| Unknown                 | Unknown — trace imports to confirm.               |