```markdown
---
tags:
  - src_utils
  - lucyproject
  - DocumentStore
  - Keywords
  - DocumentRef
  - Storage
---

## 1. Summary
The `src/utils` module provides a collection of utility functions and classes designed to facilitate document management, migration, and web scraping. Its primary responsibility is to handle operations related to document storage, context retrieval, and data migration from legacy formats. This module fits into the overall architecture by serving as a bridge between raw data sources and the application's storage layer, enabling efficient data handling and retrieval. It solves the problem of managing diverse document formats and extracting meaningful content from them, thereby enhancing the application's ability to process and utilize information effectively.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Factory Pattern**: Used in the `index_obsidian_file` and `index_obsidian_vault` functions to create `DocumentRef` instances based on parsed markdown files.
- **Strategy Pattern**: The `_generate_search_aliases` function implements two strategies for generating search aliases based on document paths and tags.
- **Dependency Injection**: The `index_obsidian_file` and `index_obsidian_vault` functions accept a `Storage` instance, allowing for flexible storage implementations.

Classes and functions within the module exhibit a high degree of cohesion, with clear responsibilities. For instance, the `get_document_context` and `get_document_context_traced` functions are closely related, with the latter extending the former's functionality by providing additional tracing information. The module does not appear to have a legacy/v2 split, indicating a relatively unified design.

Important design decisions include the use of type hints for better code clarity and the implementation of robust error handling, particularly in file operations and network requests.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| DocumentRef   | N/A         | Represents a reference to a document in storage.  |
| Storage       | N/A         | Abstract base class for storage implementations.   |
| Keywords      | N/A         | Utility class for keyword extraction.             |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                     |
|----------------------------------|---------------------------------------------------------|-------------------------------------|
| document_context.py              | Provides functions to retrieve document context snippets.| get_document_context, get_document_context_traced |
| migrate_legacy_completions.py    | Migrates legacy completion data to a new format.       | migrate                             |
| obsidian_importer.py             | Indexes Obsidian markdown files as DocumentRef entries. | index_obsidian_file, index_obsidian_vault |
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
| INPUT_PATH                   | Path("data/completions/lucy_junwin_conv.json") | Path to the input JSON file for migration.   |
| OUT_BASE                     | Path("data")                  | Base path for output files.                   |
| DEFAULT_MAX_CHARS            | 8000                           | Default maximum characters to load from a text file. |
| DEFAULT_TIMEOUT_SECONDS       | 10                             | Default timeout for web scraping requests.    |
| USER_AGENT                   | "Mozilla/5.0 ..."             | User agent string for HTTP requests.          |

## 9. Methods (by class)
### DocumentRef
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| N/A    | N/A          | N/A       | N/A         |

### Storage
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| N/A    | N/A          | N/A       | N/A         |

### Keywords
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| N/A    | N/A          | N/A       | N/A         |

### Functions
#### get_document_context
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| get_document_context | Function | `get_document_context(storage: DocumentStore, account_name: str, query: str, kind: str | None = None, docs_tag: str | None = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` | Retrieves context snippets from documents based on a query. Accepts a storage implementation, account name, and optional filters. Returns a list of dictionaries containing document details. |

#### get_document_context_traced
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| get_document_context_traced | Function | `get_document_context_traced(storage: DocumentStore, account_name: str, query: str, kind: str | None = None, docs_tag: str | None = None, limit: int = 3, max_chars: int = 6000, keywords: Any | None = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]` | Similar to `get_document_context`, but also returns a trace of the scoring process for debugging and analysis. |

#### migrate
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| migrate | Function | `migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None` | Migrates legacy completion data from a JSON file to a new structured format. Groups conversations and writes them to new JSON files. |

#### index_obsidian_file
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| index_obsidian_file | Function | `index_obsidian_file(storage: Storage, account_name: str, md_path: str | Path, vault_root: Optional[str | Path] = None, kind: str = "obsidian_note") -> list[DocumentRef]` | Indexes a single Obsidian markdown file as a DocumentRef entry. Parses the file and extracts metadata. |

#### index_obsidian_vault
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| index_obsidian_vault | Function | `index_obsidian_vault(storage: Storage, account_name: str, vault_path: str | Path, kind: str = "obsidian_note", max_files: Optional[int] = None, recursive: bool = False) -> list[DocumentRef]` | Indexes all markdown files in an Obsidian vault as DocumentRef entries. Supports recursive indexing. |

#### scrape_url
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| scrape_url | Function | `scrape_url(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str` | Scrapes text from a given URL and returns the extracted content. Handles HTTP requests and errors. |

#### load_text_snippet
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| load_text_snippet | Function | `load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]` | Loads a text file and returns a snippet of specified maximum length. Indicates if the text was truncated. |

## 10. Usage Examples
```python
from src.utils.document_context import get_document_context
from src.storage.interfaces import DocumentStore

# Assuming `storage` is an instance of a class implementing DocumentStore
contexts = get_document_context(storage, "my_account", "search query", limit=5)
print(contexts)
```

```python
from src.utils.migrate_legacy_completions import migrate

# Migrate legacy completions for a specific account
migrate(account_name="junwin")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs robust error handling, particularly in file I/O and network requests. Functions like `scrape_url` and `load_text_snippet` log warnings and return default values when exceptions occur.
- **File Existence**: Functions that read files (e.g., `index_obsidian_file`) raise `ValueError` if the specified path does not exist or is not a file.
- **Legacy Data**: The migration function assumes a specific structure for legacy data, which may lead to issues if the input format changes.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads access shared resources.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|---------------------------------------------------|
| src.main                     | Uses various utility functions for document handling and migration. |
| src.storage                  | Interacts with storage implementations for document indexing. |
| src.keywords                 | Utilizes keyword extraction for document context retrieval. |
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |
```