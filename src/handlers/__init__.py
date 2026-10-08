"""Package exports for handler implementations.

This module exposes commonly used HandlerV2 implementations at the
src.handlers package level for convenient imports (e.g.
`from src.handlers import FileLoadHandler2`). The keywords handler has
optional dependencies; import it lazily and do not raise on failure so
importing the package remains cheap in environments without NLP libs.
"""

# Import guards: many handler adapters depend on the external 'galet_tools'
# package. During testing or in constrained environments that package may not
# be available; avoid raising ImportError at package import time by importing
# defensively and exposing None for unavailable handlers.

_try_imports = []

def _safe_import(name: str, target: str):
    try:
        module = __import__(name, fromlist=[target])
        return getattr(module, target)
    except Exception:
        return None

FileLoadHandler2 = _safe_import('.file_load_handler2', 'FileLoadHandler2')
FileSaveHandler2 = _safe_import('.file_save_handler', 'FileSaveHandler2')
CommandExecutionHandler2 = _safe_import('.command_execution_handler2', 'CommandExecutionHandler2')
ScrapeWebPageHandler2 = _safe_import('.scrape_web_page_handler2', 'ScrapeWebPageHandler2')
WebSearchHandler2 = _safe_import('.web_search_handler2', 'WebSearchHandler2')
ResetSessionHandler = _safe_import('.reset_session_handler', 'ResetSessionHandler')
RemoteExecuteHandler = _safe_import('.remote_execute_handler', 'RemoteExecuteHandler')
DelegateTaskHandler = _safe_import('.delegate_task_handler', 'DelegateTaskHandler')
PatchApplyHandler = _safe_import('.patch_apply_handler', 'PatchApplyHandler')
AgentsManageHandler = _safe_import('.agents_manage_handler', 'AgentsManageHandler')

# Optional: GetKeywordsHandler depends on NLP libraries (spaCy/nltk/sklearn).
# Import defensively so consumers can still import src.handlers when those
# optional deps are not available.
GetKeywordsHandler = _safe_import('.get_keywords_handler', 'GetKeywordsHandler')

__all__ = [
    "FileLoadHandler2",
    "FileSaveHandler2",
    "CommandExecutionHandler2",
    "ScrapeWebPageHandler2",
    "WebSearchHandler2",
    "ResetSessionHandler",
    "RemoteExecuteHandler",
    "DelegateTaskHandler",
    "PatchApplyHandler",
    "AgentsManageHandler",
]

if GetKeywordsHandler is not None:
    __all__.append("GetKeywordsHandler")
