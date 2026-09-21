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
from galet_tools import HandlerRegistry, register_installed_handlers
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.scrape_web_page_handler2 import ScrapeWebPageHandler2
from src.handlers.web_search_handler2 import WebSearchHandler2
from src.handlers.tasklists_manage_handler import TasklistsManageHandler
from src.handlers.tasklists_run_handler import TasklistsRunHandler
from src.handlers.curate_chat_handler import CurateChatHandler
from src.handlers.generate_doc_handler import GenerateDocHandler
from src.handlers.sandbox_execute_handler import SandboxExecuteHandler
from src.handlers.reset_session_handler import ResetSessionHandler
from src.handlers.serve_image_handler import ServeImageHandler
from src.handlers.generate_svg_handler import GenerateSvgHandler
from src.handlers.semantic_memory_handler import SemanticMemoryHandler
from src.handlers.episodic_memory_handler import EpisodicMemoryHandler
from src.handlers.remote_execute_handler import RemoteExecuteHandler
from src.handlers.patch_apply_handler import PatchApplyHandler
from src.handlers.repo_index_handler import RepoIndexHandler
from src.handlers.repo_search_handler import RepoSearchHandler
from src.handlers.delegate_task_handler import DelegateTaskHandler
from src.handlers.tool_handler_meta_handler import ToolHandlerMetaHandler
from src.handlers.agents_manage_handler import AgentsManageHandler
from src.handlers.lazy_tool_selector_handler import LazyToolSelectorHandler
from src.handlers.tool_selection_probe_handler import ToolSelectionProbeHandler
from src.handlers.context_handler import ContextHandler
from src.handlers.video_generate_handler import VideoGenerateHandler
from src.handlers.discover_tools_handler import DiscoverToolsHandler
from src.handlers.activate_tools_handler import ActivateToolsHandler
from src.handlers.tool_catalog import RegistryToolProvider, ToolCatalog

try:
    from src.handlers.generate_image_handler import GenerateImageHandler

    _GENERATE_IMAGE_AVAILABLE = True
except ImportError:
    _GENERATE_IMAGE_AVAILABLE = False
    GenerateImageHandler = None  # type: ignore[misc]

logger = logging.getLogger(__name__)


def build_registry_and_catalog() -> tuple[HandlerRegistry, ToolCatalog]:
    """Create one execution registry and its provider-aware discovery catalog.

    Lucy-owned registrations and installed extension registrations share the
    same HandlerRegistry so existing execution and permission behavior is
    unchanged. The catalog records their source boundaries separately.
    """

    reg = HandlerRegistry()

    # Core handlers (expected to be available)
    reg.register(FileLoadHandler2)
    reg.register(FileSaveHandler2)
    reg.register(CommandExecutionHandler2)
    reg.register(ScrapeWebPageHandler2)
    reg.register(SandboxExecuteHandler)
    reg.register(GenerateSvgHandler)
    reg.register(ContextHandler)
    reg.register(RepoIndexHandler)
    reg.register(RepoSearchHandler)
    reg.register(VideoGenerateHandler)
    reg.register(DiscoverToolsHandler)
    reg.register(ActivateToolsHandler)

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

    # Tasklist management (CRUD)
    reg.register(TasklistsManageHandler)
    # Tasklist execution (run)
    reg.register(TasklistsRunHandler)
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

    # CoALA semantic memory recall — integration-test seam for Lucy agents
    reg.register(SemanticMemoryHandler)
    # CoALA episodic memory — integration-test seam over Chat2
    reg.register(EpisodicMemoryHandler)

    # Remote execution — query a remote Lucy instance's /ask endpoint
    reg.register(RemoteExecuteHandler)
    # Delegation — select an eligible machine, then use remote execution
    reg.register(DelegateTaskHandler)
    # Patch application — constrained single-file unified diffs
    reg.register(PatchApplyHandler)

    # Tool metadata inspector
    reg.register(ToolHandlerMetaHandler)

    # Agent management (list/get/upsert/delete/reload)
    reg.register(AgentsManageHandler)

    # Lazy tool-loading scaffolding (test rig)
    reg.register(LazyToolSelectorHandler)

    # Tool selection pipeline diagnostic probe (issue #126)
    reg.register(ToolSelectionProbeHandler)

    # Snapshot Lucy-owned names before extensions contribute handlers. These
    # source boundaries are catalog metadata only; every handler still executes
    # through this same registry and the existing permission filters.
    lucy_tool_names = frozenset(reg.tool_names())

    # Installed extension packages contribute handlers through the shared
    # galet_tools.handlers entry-point group. Registration does not grant an
    # agent permission: the existing agent/context allowlists still apply.
    loaded_plugins = register_installed_handlers(reg)
    if loaded_plugins:
        logger.info("Loaded handler plugins: %s", ", ".join(loaded_plugins))

    installed_tool_names = frozenset(set(reg.tool_names()) - set(lucy_tool_names))
    providers = [
        RegistryToolProvider(
            reg,
            source="lucy",
            tool_names=lucy_tool_names,
        )
    ]
    if installed_tool_names:
        providers.append(
            RegistryToolProvider(
                reg,
                source="galet-tools",
                tool_names=installed_tool_names,
            )
        )
    catalog = ToolCatalog(providers)
    # Handlers receive the registry in their execution context. Attaching the
    # paired catalog keeps discovery on the exact registry used for execution.
    reg.tool_catalog = catalog

    logger.info(
        "Handler registry built with %d handlers across %d tool sources.",
        len(reg.tool_names()),
        len(providers),
    )
    return reg, catalog


def build_registry() -> HandlerRegistry:
    """Build the execution registry (backward-compatible public API)."""

    registry, _catalog = build_registry_and_catalog()
    return registry


def build_tool_catalog() -> ToolCatalog:
    """Build a provider-aware catalog over the production registry."""

    _registry, catalog = build_registry_and_catalog()
    return catalog
