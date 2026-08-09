```markdown
---
tags:
  - src_utils
  - lucyproject
  - DocumentRef
  - Storage
  - Keywords
  - JsonFileStorage
  - Obsidian
  - Migration
  - Scraper
---

## 1. Summary
The `src/utils` module provides a collection of utility functions and classes designed to facilitate document management, migration, and web scraping within the Lucy project. Its primary responsibility is to handle various operations related to document storage, including indexing, migrating legacy data, and extracting content from web pages. This module fits into the overall architecture by serving as a bridge between raw data sources (like markdown files and web pages) and the storage layer, ensuring that documents are properly formatted and indexed for retrieval.

The module addresses the problem of efficiently managing and accessing documents from different sources, allowing users to seamlessly integrate content from Obsidian markdown files and web pages into a unified storage system.

## 2. Architecture & Design
The design of the `src/utils` module employs several key patterns and practices:

- **Factory Pattern**: The `index_obsidian_file` and `index_obsidian_vault` functions act as factories for creating `DocumentRef` instances, encapsulating the logic for document creation and storage.
- **Separation of Concerns**: Each function has a single responsibility, whether it's scraping a webpage, migrating legacy data, or indexing documents. This modular approach enhances maintainability and testability.
- **Error Handling**: The module employs robust error handling, particularly in file operations and network requests, ensuring that failures are logged and do not crash the application.
- **Dependency Injection**: The `Storage` class is passed as a parameter to various functions, allowing for flexibility in the storage implementation used (e.g., JSON file storage or a database).

The classes and functions within the module are designed to work together through composition. For instance, the `load_text_snippet` function is used by `get_document_context` to retrieve snippets from documents, demonstrating a clear relationship between utility functions.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| DocumentRef   | None        | Represents a reference to a document in storage.  |
| Storage       | None        | Abstract base class for storage implementations.   |
| Keywords      | None        | Utility for keyword extraction from text.          |

## 4. Source Files
| File                             | Responsibility                                           | Notable Exports                     |
|----------------------------------|---------------------------------------------------------|-------------------------------------|
| `document_context.py`            | Provides functions to retrieve document context snippets.| `get_document_context`, `get_document_context_traced` |
| `migrate_legacy_completions.py` | Handles migration of legacy completion data to new format.| `migrate`                          |
| `obsidian_importer.py`          | Indexes Obsidian markdown files into storage.          | `index_obsidian_file`, `index_obsidian_vault` |
| `scrape.py`                     | Scrapes text content from web pages.                   | `scrape_url`, `extract_text_from_html` |
| `text_snippet_loader.py`        | Loads text snippets from files.                         | `load_text_snippet`                |

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
  - `src.utils.text_snippet_loader`
  - `src.keywords.keywords`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls                      |
|--------------------|--------|---------|---------------------------------------|
| None               | -      | -       | None                                  |

## 7. Exceptions
| Exception          | Base   | When Raised                               |
|--------------------|--------|-------------------------------------------|
| None               | -      | None                                      |

## 8. Module-Level Constants
| Constant                     | Value                          | Description                                      |
|------------------------------|--------------------------------|--------------------------------------------------|
| `DEFAULT_MAX_CHARS`          | 8000                           | Default maximum characters to load from a text file. |
| `DEFAULT_TIMEOUT_SECONDS`     | 10                             | Default timeout for web scraping requests.       |
| `INPUT_PATH`                 | `Path("data/completions/lucy_junwin_conv.json")` | Path to the input JSON file for migration.      |
| `OUT_BASE`                   | `Path("data")`                | Base path for output files during migration.     |

## 9. Methods (by class)
### DocumentRef
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `__init__` | Instance | `def __init__(self, id: str, account_name: str, path: str, kind: str, title: str, tags: list[str], metadata: dict)` | Initializes a DocumentRef instance with the provided attributes. |

### Storage
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `upsert_document` | Instance | `def upsert_document(self, doc: DocumentRef) -> None` | Inserts or updates a document in the storage. |

### Keywords
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `extract_keywords` | Instance | `def extract_keywords(self, text: str, top_n: int) -> list[str]` | Extracts keywords from the provided text. |

### Functions
#### document_context.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `get_document_context` | Function | `def get_document_context(storage: Storage, account_name: str, query: str, kind: Optional[str] = None, docs_tag: Optional[str] = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` | Retrieves context snippets from documents based on a query. |
| `get_document_context_traced` | Function | `def get_document_context_traced(storage: Storage, account_name: str, query: str, kind: Optional[str] = None, docs_tag: Optional[str] = None, limit: int = 3, max_chars: int = 6000, keywords: Optional[Any] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]` | Retrieves context snippets and a scoring trace for documents. |

#### migrate_legacy_completions.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `migrate` | Function | `def migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None` | Migrates legacy completion data to a new format. |

#### obsidian_importer.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `index_obsidian_file` | Function | `def index_obsidian_file(storage: Storage, account_name: str, md_path: str | Path, vault_root: Optional[str | Path] = None, kind: str = "obsidian_note") -> list[DocumentRef]` | Indexes a single Obsidian markdown file. |
| `index_obsidian_vault` | Function | `def index_obsidian_vault(storage: Storage, account_name: str, vault_path: str | Path, kind: str = "obsidian_note", max_files: Optional[int] = None, recursive: bool = False) -> list[DocumentRef]` | Indexes all markdown files in an Obsidian vault. |

#### scrape.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `scrape_url` | Function | `def scrape_url(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str` | Scrapes text content from a given URL. |
| `extract_text_from_html` | Function | `def extract_text_from_html(html: str) -> str` | Extracts readable text from HTML content. |

#### text_snippet_loader.py
| Method | Type         | Signature | Description |
|--------|--------------|-----------|-------------|
| `load_text_snippet` | Function | `def load_text_snippet(path: str | Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]` | Loads a text file and returns a snippet of specified length. |

## 10. Usage Examples
### Indexing an Obsidian File
```python
from src.storage.base import JsonFileStorage
from src.utils.obsidian_importer import index_obsidian_file

storage = JsonFileStorage()
account_name = "user_account"
md_path = "path/to/your/obsidian_note.md"

indexed_docs = index_obsidian_file(storage, account_name, md_path)
print(indexed_docs)
```

### Migrating Legacy Completions
```python
from src.utils.migrate_legacy_completions import migrate

migrate(account_name="junwin", agent_name="lucy")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-safe approach, logging errors without crashing the application. For instance, if a file cannot be read, it logs a warning and returns an empty result.
- **Legacy Migration**: The migration function assumes a specific structure of the legacy data. If the structure changes, it may lead to unexpected results or failures.
- **Thread Safety**: The module does not explicitly handle thread safety. If multiple threads access the same storage instance, it may lead to race conditions.
- **File Encoding**: When reading files, the module uses UTF-8 encoding but does not handle all possible encoding issues, which may lead to data loss or corruption.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|---------------------------------------------------|
| `src.main`                   | Calls functions from `src.utils` for document management. |
| `src.storage`                | Utilizes `DocumentRef` and `Storage` for document handling. |
| `src.keywords`               | Uses `Keywords` for keyword extraction in document processing. |
| Unknown — trace imports to confirm. | - |
```