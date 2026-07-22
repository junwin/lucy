# Module Documentation for `src/curation`

## YAML Front Matter
```yaml
tags:
  - src_curation
  - lucyproject
  - CurationEngine
  - ChatEvent
  - LLMApi
  - ChatSessionMeta
```

## 1. Summary
The `src.curation` module provides a comprehensive framework for managing chat session curation, including digest creation, archiving, and filtering operations. It serves as a core component of the larger architecture, facilitating the processing and summarization of chat events into structured formats. The module addresses the need for efficient session management, allowing users to distill conversations into meaningful summaries, archive original events, and apply filtering rules to enhance the relevance of stored data.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Facade Pattern**: The `CurationEngine` class acts as a facade, wrapping various functionalities (resolver, summarizer, archiver, and template renderer) into a single interface.
- **Strategy Pattern**: Different modes of operation (filtering, summarizing, archiving) are implemented as private methods within `CurationEngine`, allowing for flexible behavior based on user input.
- **Dependency Injection**: The use of `Chat2Store` and `LLMApi` as dependencies in the `CurationEngine` constructor promotes loose coupling and enhances testability.

Classes within the module exhibit a composition relationship, where `CurationEngine` utilizes other classes like `ChatEvent`, `LLMApi`, and functions from the `resolver`, `summarizer`, `archiver`, and `templates` modules. There is no evident legacy/v2 split, indicating a cohesive design.

Key design decisions include the use of structured logging for error handling and the implementation of a fallback mechanism in the summarization process to ensure robustness.

## 3. Key Classes
| Class            | Base/Parent | Purpose                                                                 |
|------------------|-------------|-------------------------------------------------------------------------|
| CurationEngine    | None        | Orchestrates chat curation operations, including filtering, summarizing, and archiving. |
| ChatEvent         | None        | Represents individual chat events, encapsulating their properties and behaviors. |
| LLMApi            | None        | Interface for interacting with the LLM for summarization tasks.        |
| ChatSessionMeta   | None        | Metadata structure for chat sessions, used in session resolution.      |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                                                                 |
|-----------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`              | Initializes the curation module and exports core functions. | CurationEngine, resolve_session, render_template, resolve_template, summarize_session, archive_session |
| `archiver.py`              | Handles archiving of chat sessions.                     | archive_session                                                                  |
| `core.py`                  | Main orchestration logic for curation operations.      | CurationEngine                                                                   |
| `resolver.py`              | Resolves sessions by ID or friendly name.              | resolve_session                                                                  |
| `summarizer.py`            | Summarizes chat events into structured digests.        | summarize_session                                                                |
| `templates.py`             | Manages template rendering for digests.                | render_template, resolve_template                                                |

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
  - `src.llm.interface`
  - `src.llm.dto`

- **Optional dependencies**: 
  - None identified.

## 6. Configuration / Settings
| Key                     | Type    | Default                     | What it controls                                      |
|-------------------------|---------|-----------------------------|------------------------------------------------------|
| None                    | None    | None                        | None                                                 |

## 7. Exceptions
| Exception               | Base    | When Raised                |
|-------------------------|---------|----------------------------|
| None                    | None    | None                       |

## 8. Module-Level Constants
| Constant                | Value   | Description                |
|-------------------------|---------|----------------------------|
| SUMMARIZE_SYSTEM_PROMPT | String  | System prompt for LLM summarization. |

## 9. Methods (by class)

### CurationEngine
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`             | Instance    | `def __init__(self, chat2_store: Chat2Store, llm_api: LLMApi, ...)`    | Initializes the CurationEngine with dependencies and configuration settings.                                                                                                                              |
| `curate`                | Instance    | `def curate(self, session_id: Optional[str], ...)`                      | Runs curation on a session, allowing for filtering, summarizing, or archiving based on the provided mode. Returns a dictionary with the result status and relevant data.                                                                 |
| `_mode_filter`          | Instance    | `def _mode_filter(self, sid: str, events: List[ChatEvent], ...)`       | Applies filtering rules to the session events and updates the session with the filtered events. Returns a summary of the filtering operation.                                                                 |
| `_mode_summarize`       | Instance    | `def _mode_summarize(self, sid: str, events: List[ChatEvent], ...)`    | Generates a digest of the session events using the LLM and optionally writes it to disk. Returns a dictionary with the status and generated note text.                                                                 |
| `_mode_archive`         | Instance    | `def _mode_archive(self, sid: str, events: List[ChatEvent], ...)`      | Summarizes the session, archives original events, and replaces them with a digest. Returns a dictionary with the status and output path.                                                                 |
| `_write_digest`         | Instance    | `def _write_digest(self, session_id: str, account: str, note_text: str)` | Writes the generated digest to a file and returns the output path.                                                                                                                                       |

### ChatEvent
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Represents individual chat events.                                                                                                                                                                        |

### LLMApi
| Method                  | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-------------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| None                    | None        | None                                                                      | Interface for interacting with the LLM for summarization tasks.                                                                                                                                         |

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
curation_engine = CurationEngine(chat2_store, llm_api)

# Curate a session
result = curation_engine.curate(session_id="12345", account="user_account", mode="summarize", publish=True)
print(result)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs structured logging for error handling, particularly in the `archive_session` and `summarize_session` functions, ensuring that failures are logged appropriately.
- **Fallback Mechanisms**: In the summarization process, if the LLM fails to generate a digest, a fallback method is invoked to create a simple text digest.
- **Thread Safety**: The module does not explicitly mention thread safety; care should be taken when using shared resources like `Chat2Store`.
- **Known Limitations**: The maximum character limit for LLM input is enforced in the `_build_events_text` function to avoid exceeding context window limits.

## 12. Consumers
| Consumer                | What it uses                                                                 |
|-------------------------|-------------------------------------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |