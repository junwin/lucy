```markdown
---
tags:
  - src_utils
  - lucyproject
  - DocumentStore
  - Keywords
  - DocumentRef
---

## 1. Summary
The `src/utils` module provides a collection of utility functions and classes designed to facilitate document management and processing within the Lucy project. Its primary responsibility is to handle various operations related to document storage, migration, and indexing, particularly for markdown files used in the Obsidian note-taking application. This module fits into the overall architecture by serving as a bridge between user-generated content and the underlying storage mechanisms, ensuring that documents can be efficiently retrieved, indexed, and migrated.

The module addresses the problem of managing and processing documents in a structured manner, allowing users to easily access and manipulate their notes and related content. It provides functionalities such as scraping web pages, loading text snippets, and migrating legacy data formats, thereby enhancing the overall user experience.

## 2. Architecture & Design
The design of the `src/utils` module employs several key design patterns and principles:

- **Factory Pattern**: The `index_obsidian_file` and `index_obsidian_vault` functions act as factories for creating `DocumentRef` instances, encapsulating the logic for document creation and storage.
- **Separation of Concerns**: Each utility function is focused on a specific task, such as scraping, indexing, or migrating data, which promotes maintainability and readability.
- **Error Handling**: The module employs robust error handling, particularly in file operations and network requests, ensuring that failures are logged and managed gracefully.

Classes and functions within the module often interact through composition, where utility functions are called within other functions to achieve complex behaviors. For instance, the `load_text_snippet` function is used within the document context retrieval functions to load content from files.

There is no explicit legacy/v2 split in the module, but the presence of migration functions indicates a consideration for backward compatibility with older data formats.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| DocumentRef   | N/A         | Represents a reference to a document in storage.  |
| Keywords      | N/A         | Utility for extracting keywords from text.        |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                     |
|----------------------------------|---------------------------------------------------------|-------------------------------------|
| document_context.py              | Provides functions to retrieve document context snippets.| get_document_context, get_document_context_traced |
| migrate_legacy_completions.py    | Handles migration of legacy completion data to new format.| migrate                             |
| obsidian_importer.py            | Indexes Obsidian markdown files as DocumentRef entries. | index_obsidian_file, index_obsidian_vault |
| scrape.py                        | Scrapes text from web pages.                            | scrape_url, main                   |
| text_snippet_loader.py           | Loads text snippets from files.                         | load_text_snippet                  |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `datetime`
  - `pathlib`
  - `collections`
  - `logging`
  - `re`
  - `sys`
- **Third-party packages**:
  - `requests`
  - `bs4` (BeautifulSoup)
  - `yaml`
- **Internal modules**:
  - `src.storage.interfaces`
  - `src.storage.base`
  - `src.storage.models`
  - `src.utils.text_snippet_loader`
  - `src.keywords.keywords`
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls                      |
|--------------------|--------|---------|---------------------------------------|
| None               | N/A    | N/A     | None                                  |

## 7. Exceptions
| Exception         | Base         | When Raised                                      |
|-------------------|--------------|-------------------------------------------------|
| None              | N/A          | None                                            |

## 8. Module-Level Constants
| Constant                     | Value                          | Description                                   |
|------------------------------|--------------------------------|-----------------------------------------------|
| DEFAULT_MAX_CHARS            | 8000                           | Default maximum characters to load from a text file. |
| DEFAULT_TIMEOUT_SECONDS       | 10                             | Default timeout for web scraping requests.    |
| INPUT_PATH                   | Path("data/completions/lucy_junwin_conv.json") | Path to the input JSON file for migration.    |
| OUT_BASE                     | Path("data")                  | Base path for output files during migration.  |

## 9. Methods (by class)

### DocumentRef
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| N/A    | N/A          | N/A       | N/A         |

### Keywords
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| N/A    | N/A          | N/A       | N/A         |

### Functions
#### document_context.py
| Method                       | Type         | Signature                                                                 | Description |
|------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| get_document_context          | Function     | `get_document_context(storage: DocumentStore, account_name: str, query: str, kind: Optional[str] = None, docs_tag: Optional[str] = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` | Retrieves context snippets from documents based on a query. |
| get_document_context_traced   | Function     | `get_document_context_traced(storage: DocumentStore, account_name: str, query: str, kind: Optional[str] = None, docs_tag: Optional[str] = None, limit: int = 3, max_chars: int = 6000, keywords: Optional[Any] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]` | Similar to `get_document_context`, but returns a trace of the scoring process. |

#### migrate_legacy_completions.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| migrate | Function     | `migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None` | Migrates legacy completion data to a new format. |

#### obsidian_importer.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| index_obsidian_file | Function | `index_obsidian_file(storage: Storage, account_name: str, md_path: str | Path, vault_root: Optional[str | Path] = None, kind: str = "obsidian_note") -> list[DocumentRef]` | Indexes a single Obsidian markdown file as a DocumentRef entry. |
| index_obsidian_vault | Function | `index_obsidian_vault(storage: Storage, account_name: str, vault_path: str | Path, kind: str = "obsidian_note", max_files: Optional[int] = None, recursive: bool = False) -> list[DocumentRef]` | Indexes all .md files in an Obsidian vault as DocumentRef entries. |

#### scrape.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| scrape_url | Function | `scrape_url(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str` | Scrapes text from a given URL. |
| main | Function | `main(argv: Optional[list[str]] = None) -> int` | Main entry point for the script, handling command-line arguments. |

#### text_snippet_loader.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| load_text_snippet | Function | `load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]` | Loads a text file and returns a snippet of specified maximum length. |

## 10. Usage Examples
```python
from src.utils.document_context import get_document_context
from src.storage.interfaces import DocumentStore

# Assuming `storage` is an instance of DocumentStore
contexts = get_document_context(storage, "my_account", "search query", limit=5)
print(contexts)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach in many functions, raising exceptions for invalid inputs (e.g., non-existent files or directories).
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads access shared resources.
- **Legacy Data**: The migration functions are designed to handle legacy data formats, but users should ensure that the input data adheres to expected structures to avoid runtime errors.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|---------------------------------------------------|
| src.main                     | Imports various utility functions for document processing. |
| src.storage                  | Utilizes DocumentRef and storage interfaces for document management. |
| src.keywords                 | Uses Keywords for extracting keywords from text. |
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |
```