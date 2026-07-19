"""Build and populate the HandlerRegistry with available HandlerV2 implementations.

This module imports concrete handlers and registers them with the registry so
that the rest of the application can discover and instantiate handlers by
name. Keep imports local to module-level to avoid circular imports when
handlers import other parts of the system.

Handlers that require optional heavy dependencies (e.g., spaCy, sklearn)
are imported lazily so the registry can be built in environments where
those packages are not installed. Such handlers will be skipped and a
warning logged.
"""

import logging
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.scrape_web_page_handler2 import ScrapeWebPageHandler2
from src.handlers.web_search_handler2 import WebSearchHandler2
from src.handlers.delegate_tasks_handler import DelegateTasksHandler
from src.handlers.tasklists_manage_handler import TasklistsManageHandler
from src.handlers.tasklists_run_handler import TasklistsRunHandler
from src.handlers.chat2_handler import Chat2Handler
from src.handlers.curate_chat_handler import CurateChatHandler
from src.handlers.generate_doc_handler import GenerateDocHandler
from src.handlers.sandbox_execute_handler import SandboxExecuteHandler
from src.handlers.reset_session_handler import ResetSessionHandler
from src.handlers.serve_image_handler import ServeImageHandler
from src.handlers.generate_svg_handler import GenerateSvgHandler

try:
    from src.handlers.generate_image_handler import GenerateImageHandler

    _GENERATE_IMAGE_AVAILABLE = True
except ImportError:
    _GENERATE_IMAGE_AVAILABLE = False
    GenerateImageHandler = None  # type: ignore[misc]

logger = logging.getLogger(__name__)


def build_registry() -> HandlerRegistry:
    """Create and populate a HandlerRegistry.

    Returns a HandlerRegistry populated with available handlers. Handlers
    that fail to import due to optional dependencies will be skipped and
    logged, rather than causing an import-time failure.
    """

    reg = HandlerRegistry()

    # Core handlers (expected to be available)
    reg.register(FileLoadHandler2)
    reg.register(FileSaveHandler2)
    reg.register(CommandExecutionHandler2)
    reg.register(ScrapeWebPageHandler2)
    reg.register(SandboxExecuteHandler)
    reg.register(GenerateSvgHandler)

    # Optional / third-party dependent handlers: import and register lazily.
    try:
        # Web search may depend on external configuration; keep optional.
        reg.register(WebSearchHandler2)
    except Exception:
        logger.debug("WebSearchHandler2 not registered (optional handler).", exc_info=True)

    try:
        # Keywords handler depends on NLP libraries (spaCy, nltk, sklearn).
        from src.handlers.get_keywords_handler import GetKeywordsHandler

        reg.register(GetKeywordsHandler)
    except Exception:
        logger.warning(
            "GetKeywordsHandler not registered: optional NLP dependencies missing or failed to import.\n"
            "Install spaCy/nltk/scikit-learn and ensure models/data are available to enable this handler.",
            exc_info=True,
        )

    # Task delegation handler (should be lightweight)
    reg.register(DelegateTasksHandler)
    # Tasklist management (CRUD)
    reg.register(TasklistsManageHandler)
    # Tasklist execution (run)
    reg.register(TasklistsRunHandler)
    # Chat2 session management
    reg.register(Chat2Handler)
    # Chat curation (summarize, archive, filter)
    reg.register(CurateChatHandler)
    # Doc generation (LLM-powered module documentation)
    reg.register(GenerateDocHandler)
    # Session reset action (SSE Phase 2)
    reg.register(ResetSessionHandler)

    # Image serving — reads existing image files from disk
    reg.register(ServeImageHandler)

    # Image generation (SSE Phase 3) — Pillow is an optional dependency
    if _GENERATE_IMAGE_AVAILABLE and GenerateImageHandler is not None:
        reg.register(GenerateImageHandler)
    else:
        logger.warning(
            "GenerateImageHandler not registered: Pillow (PIL) not available. "
            "Install with: pip install Pillow"
        )

    logger.info("Handler registry built with %d handlers.", len(reg.tool_names()))
    return reg
