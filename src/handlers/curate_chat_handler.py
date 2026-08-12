"""curate_chat handler — HandlerV2-compliant, callable by agents via FCP.

Supports three curation modes:
- filter: rule-based event removal (existing behavior)
- summarize: LLM distills session into structured Markdown digest
- archive: summarize + move original to archive + replace with digest event
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.curation.core import CurationEngine
from src.curation.resolver import resolve_session
from src.embeddings.facade import EmbeddingFacade
from src.llm.interface import LLMApi
from src.llm.router_api import RouterApi

logger = logging.getLogger(__name__)

# Default max_chars for the events text block fed to the LLM during summarization.
DEFAULT_MAX_CHARS = 32000


class CurateChatHandler(HandlerV2):
    """Handler for chat curation (summarize, archive, filter).

    Invoked by agents via FunctionCallingProcessor.
    """

    NAME = "curate_chat"

    def __init__(self, config: ConfigManager):
        self.config = config
        self.chat2_store = self._build_store()
        self.llm_api: LLMApi = RouterApi()
        self.engine = self._build_engine()

    @staticmethod
    def _build_store():
        """Construct a Chat2Store from config."""
        from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
        from src.chat2.facade import Chat2Store
        from src.storage.json_file_storage import JsonFileStorage
        from src.storage_paths.storage_paths import StoragePaths

        cfg = ConfigManager("config.json")
        storage_root = cfg.get("storage_root_path") or "/home/junwin/lucydata"
        storage_ns = cfg.get("storage_namespace") or "data"
        sp = StoragePaths(storage_root, storage_ns)
        storage = JsonFileStorage(sp)
        adapter = JfsChat2Primitives(storage)
        return Chat2Store(adapter)

    def _build_engine(self) -> CurationEngine:
        """Build the curation engine with paths from config."""
        from src.storage.json_file_storage import JsonFileStorage
        from src.storage_paths.storage_paths import StoragePaths

        # Determine external root for lucy_data_files
        external_roots = self.config.get("external_roots", {})
        lucy_data_root = external_roots.get("lucy_data_files", "/home/junwin/lucy_storage")

        data_base = Path(lucy_data_root) / "data"

        # Determine account from config or default
        # The handler receives account_name at runtime, so we use a placeholder
        # and resolve paths per-call in the engine.

        llm_model = self.config.get("curation_llm_model", "gpt-4o-mini")

        # Build embedding facade and storage for digest embeddings
        embedding_facade = EmbeddingFacade()
        storage_root = self.config.get("storage_root_path") or "/home/junwin/lucydata"
        storage_ns = self.config.get("storage_namespace") or "data"
        sp = StoragePaths(storage_root, storage_ns)
        storage = JsonFileStorage(sp)

        return CurationEngine(
            chat2_store=self.chat2_store,
            llm_api=self.llm_api,
            llm_model=llm_model,
            digests_root=data_base / "digests",
            archives_root=data_base / "archives",
            embedding_facade=embedding_facade,
            storage=storage,
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Curate a chat session: filter events, generate an LLM digest, "
                "or archive the session. Supports preview (dry-run) and publish modes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "friendly_name": {
                        "type": "string",
                        "description": "Friendly name of the session to curate (case-insensitive).",
                        "default": "",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Direct session UUID (takes precedence over friendly_name).",
                        "default": "",
                    },
                    "account": {
                        "type": "string",
                        "description": "Account name (e.g. 'junwin').",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["filter", "summarize", "archive"],
                        "description": (
                            "Curation mode: 'filter' removes events by rules, "
                            "'summarize' generates an LLM digest (session unchanged), "
                            "'archive' summarizes and replaces session with digest."
                        ),
                        "default": "filter",
                    },
                    "preview": {
                        "type": "boolean",
                        "description": "If true, return note_text without writing to disk.",
                        "default": True,
                    },
                    "publish": {
                        "type": "boolean",
                        "description": "If true, write the digest to data/digests/<account>/.",
                        "default": False,
                    },
                    "template_name": {
                        "type": "string",
                        "description": "Named template to use for digest formatting.",
                        "default": "default",
                    },
                    "curation_rules": {
                        "type": "string",
                        "description": (
                            "JSON string of curation rules (for filter mode). "
                            "Supports: remove_kinds (list), keep_roles (list), deduplicate (bool)."
                        ),
                        "default": "",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": (
                            "Max characters for the events text block fed to the LLM "
                            "during summarize/archive modes (default from config or 32000)."
                        ),
                        "default": 32000,
                    },
                },
                "required": [
                    "friendly_name",
                    "session_id",
                    "account",
                    "mode",
                    "preview",
                    "publish",
                    "template_name",
                    "curation_rules",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "status": {"type": "string"},
                "note_text": {"type": "string"},
                "output_path": {"type": "string"},
                "session_id": {"type": "string"},
                "summary": {"type": "object"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:
        """Execute curation.

        Args:
            args: Tool arguments (friendly_name, session_id, account, mode, etc.)
            account_name: Injected by FCP (used as fallback for account).

        Returns:
            Result dict.
        """
        friendly_name = (args.get("friendly_name") or "").strip()
        session_id = (args.get("session_id") or "").strip()
        account = (args.get("account") or account_name or "").strip()
        mode = (args.get("mode") or "filter").strip().lower()
        preview = bool(args.get("preview", True))
        publish = bool(args.get("publish", False))
        template_name = (args.get("template_name") or "default").strip()
        curation_rules_raw = args.get("curation_rules") or ""

        # max_chars: caller arg → config.json → module-level default
        config_default = self.config.get("curation_max_chars", DEFAULT_MAX_CHARS)
        max_chars = int(args.get("max_chars", config_default))

        if not account:
            return {
                "ok": False,
                "tool": self.NAME,
                "status": "error",
                "error": "account is required",
            }

        if not session_id and not friendly_name:
            return {
                "ok": False,
                "tool": self.NAME,
                "status": "error",
                "error": "Either session_id or friendly_name is required",
            }

        # Parse curation rules
        curation_rules: Dict[str, Any] = {}
        if curation_rules_raw:
            try:
                curation_rules = json.loads(curation_rules_raw)
            except json.JSONDecodeError as e:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "status": "error",
                    "error": f"Invalid curation_rules JSON: {e}",
                }

        logger.info(
            "curate_chat: account=%s mode=%s friendly_name=%s session_id=%s preview=%s publish=%s max_chars=%d",
            account,
            mode,
            friendly_name,
            session_id,
            preview,
            publish,
            max_chars,
        )

        try:
            result = self.engine.curate(
                session_id=session_id or None,
                friendly_name=friendly_name or None,
                account=account,
                mode=mode,
                preview=preview,
                publish=publish,
                template_name=template_name,
                curation_rules=curation_rules,
                max_chars=max_chars,
            )

            ok = result.get("status") != "error"
            return {
                "ok": ok,
                "tool": self.NAME,
                **result,
            }

        except Exception as e:
            logger.exception("curate_chat: unexpected error")
            return {
                "ok": False,
                "tool": self.NAME,
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
            }
