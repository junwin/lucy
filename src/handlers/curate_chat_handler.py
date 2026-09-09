"""curate_chat handler — thin HandlerV2 facade over ``CurationEngine``."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.config_manager import ConfigManager
from src.curation.container_factory import get_curation_engine
from src.curation.core import CurationEngine
from src.handlers.handler_v2 import HandlerV2

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 32000


class CurateChatHandler(HandlerV2):
    """Handler for chat curation (summarize, archive, filter).

    The handler owns request validation only. Storage/provider construction is
    delegated to the application composition root and the curation algorithm
    lives in ``CurationEngine``.
    """

    NAME = "curate_chat"

    def __init__(
        self,
        config: ConfigManager,
        engine: Optional[CurationEngine] = None,
    ) -> None:
        self.config = config
        self.engine = engine

    def _engine(self, context: Dict[str, Any]) -> CurationEngine:
        injected = context.get("curation_engine")
        if isinstance(injected, CurationEngine):
            return injected
        if self.engine is not None:
            return self.engine
        return get_curation_engine()

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
                        "description": "If true, write the digest to the configured digest store.",
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
                            "during summarize/archive modes."
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
                    "max_chars",
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

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context: Any,
    ) -> Dict[str, Any]:
        friendly_name = (args.get("friendly_name") or "").strip()
        session_id = (args.get("session_id") or "").strip()
        account = (args.get("account") or account_name or "").strip()
        mode = (args.get("mode") or "filter").strip().lower()
        preview = bool(args.get("preview", True))
        publish = bool(args.get("publish", False))
        template_name = (args.get("template_name") or "default").strip()
        curation_rules_raw = args.get("curation_rules") or ""

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

        curation_rules: Dict[str, Any] = {}
        if curation_rules_raw:
            try:
                curation_rules = json.loads(curation_rules_raw)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "status": "error",
                    "error": f"Invalid curation_rules JSON: {exc}",
                }

        try:
            result = self._engine(context).curate(
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
            return {
                "ok": result.get("status") != "error",
                "tool": self.NAME,
                **result,
            }
        except Exception as exc:
            logger.exception("curate_chat: unexpected error")
            return {
                "ok": False,
                "tool": self.NAME,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
