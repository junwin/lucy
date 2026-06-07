"""Package exports for handler implementations.

This module exposes commonly used HandlerV2 implementations at the
src.handlers package level for convenient imports (e.g.
`from src.handlers import FileLoadHandler2`). The keywords handler has
optional dependencies; import it lazily and do not raise on failure so
importing the package remains cheap in environments without NLP libs.
"""

from .file_load_handler2 import FileLoadHandler2
from .file_save_handler import FileSaveHandler2
from .command_execution_handler2 import CommandExecutionHandler2
from .scrape_web_page_handler2 import ScrapeWebPageHandler2
from .web_search_handler2 import WebSearchHandler2
from .delegate_tasks_handler import DelegateTasksHandler
from .chat2_handler import Chat2Handler

# Optional: GetKeywordsHandler depends on NLP libraries (spaCy/nltk/sklearn).
# Import defensively so consumers can still import src.handlers when those
# optional deps are not available.
try:
    from .get_keywords_handler import GetKeywordsHandler
except Exception:  # pragma: no cover - platform/environment dependent
    GetKeywordsHandler = None

__all__ = [
    "FileLoadHandler2",
    "FileSaveHandler2",
    "CommandExecutionHandler2",
    "ScrapeWebPageHandler2",
    "WebSearchHandler2",
    "DelegateTasksHandler",
    "Chat2Handler",
]

if GetKeywordsHandler is not None:
    __all__.append("GetKeywordsHandler")
