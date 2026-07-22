```markdown
---
tags:
  - src_utils
  - lucyproject
  - DocumentRef
  - Storage
  - Keywords
  - TextSnippetLoader
---

## 1. Summary
The `src/utils` module provides a collection of utility functions and classes designed to facilitate document management, migration, and web scraping. Its primary responsibility is to handle various operations related to document storage, including indexing, migrating legacy data, and extracting content from markdown files and web pages. This module fits into the overall architecture by serving as a backend utility layer that interacts with storage systems and external data sources, thereby solving the problem of efficiently managing and retrieving document-related information.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Factory Pattern**: The `index_obsidian_file` and `index_obsidian_vault` functions act as factories for creating `DocumentRef` instances based on the content of markdown files.
- **Strategy Pattern**: The `_generate_search_aliases` function implements two strategies for generating search aliases based on document paths and tags.
- **Dependency Injection**: The `Storage` class is injected into various functions to abstract the underlying storage mechanism, allowing for flexibility in implementation.

Classes and functions within the module often adhere to protocols, such as the `Storage` interface, ensuring that they can work with different storage backends. The module does not appear to have a legacy/v2 split, indicating a cohesive design. Important design decisions include the use of logging for error handling and the careful management of file paths and metadata.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| DocumentRef   | None        | Represents a reference to a document in storage.  |
| Storage       | None        | Abstract base class for storage implementations.   |
| Keywords      | None        | Utility class for keyword extraction.              |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                     |
|----------------------------------|---------------------------------------------------------|-------------------------------------|
| document_context.py              | Provides functions to retrieve document context snippets.| get_document_context, get_document_context_traced |
| migrate_legacy_completions.py    | Migrates legacy conversation data to a new format.     | migrate                             |
| obsidian_importer.py            | Indexes Obsidian markdown files as DocumentRef entries. | index_obsidian_file, index_obsidian_vault |
| scrape.py                        | Scrapes text from web pages.                            | scrape_url, main                   |
| text_snippet_loader.py           | Loads text snippets from files.                         | load_text_snippet                  |
| __init__.py                     | Initializes the utils module.                           | (exports nothing)                  |

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
  - `src.storage.base`
  - `src.storage.models`
  - `src.keywords.keywords`
- **Optional dependencies**: None.

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls                      |
|--------------------|--------|---------|---------------------------------------|
| None               | None   | None    | None                                  |

## 7. Exceptions
| Exception          | Base         | When Raised                                      |
|--------------------|--------------|-------------------------------------------------|
| None               | None         | None                                            |

## 8. Module-Level Constants
| Constant                     | Value                          |
|------------------------------|--------------------------------|
| DEFAULT_MAX_CHARS            | 8000                           |
| INPUT_PATH                   | Path("data/completions/lucy_junwin_conv.json") |
| OUT_BASE                     | Path("data")                  |
| DEFAULT_TIMEOUT_SECONDS       | 10                            |
| USER_AGENT                   | "Mozilla/5.0 ..."             |

## 9. Methods (by class)
### DocumentRef
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| None   | None         | None      | None        |

### Storage
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| None   | None         | None      | None        |

### Keywords
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| None   | None         | None      | None        |

### Functions
#### document_context.py
| Method                          | Type         | Signature                                                                 | Description |
|---------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| get_document_context            | Function     | get_document_context(storage: Storage, account_name: str, query: str, ...) | Retrieves context snippets from documents based on a query. |
| get_document_context_traced     | Function     | get_document_context_traced(storage: Storage, account_name: str, query: str, ...) | Similar to get_document_context but returns a scoring trace. |

#### migrate_legacy_completions.py
| Method                          | Type         | Signature                                                                 | Description |
|---------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| migrate                         | Function     | migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None | Migrates legacy conversation data to a new format. |

#### obsidian_importer.py
| Method                          | Type         | Signature                                                                 | Description |
|---------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| index_obsidian_file             | Function     | index_obsidian_file(storage: Storage, account_name: str, md_path: str, ...) | Indexes a single Obsidian markdown file as a DocumentRef entry. |
| index_obsidian_vault            | Function     | index_obsidian_vault(storage: Storage, account_name: str, vault_path: str, ...) | Indexes all .md files in an Obsidian vault as DocumentRef entries. |

#### scrape.py
| Method                          | Type         | Signature                                                                 | Description |
|---------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| scrape_url                     | Function     | scrape_url(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str | Scrapes text from a given URL. |
| main                            | Function     | main(argv: Optional[list[str]] = None) -> int                           | Main entry point for the script. |

#### text_snippet_loader.py
| Method                          | Type         | Signature                                                                 | Description |
|---------------------------------|--------------|---------------------------------------------------------------------------|-------------|
| load_text_snippet               | Function     | load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool] | Loads a text file and returns a snippet. |

## 10. Usage Examples
```python
from src.utils.document_context import get_document_context

storage = ...  # Your storage implementation
account_name = "user_account"
query = "search term"
contexts = get_document_context(storage, account_name, query)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs logging for error handling, particularly in file reading and network requests. It is designed to fail gracefully, returning empty results or logging warnings instead of raising exceptions.
- **File Path Management**: Care must be taken to ensure that file paths are correctly resolved, especially when dealing with relative paths in the `index_obsidian_file` and `index_obsidian_vault` functions.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads are accessing shared resources.

## 12. Consumers
| Consumer                        | What it uses                                      |
|---------------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |
```