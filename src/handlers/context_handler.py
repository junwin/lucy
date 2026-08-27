"""context_handler — manage conversation contexts stored as Markdown + YAML.

A context ("whiteboard") is a Markdown file under contexts/<account>/<name>.md.
The YAML frontmatter holds operational keys (allowed_tools, mandatory_tools,
imports, tag, etc.) and the body is the context text.

Actions
-------
- list                 : list context names for the account (default limit 200)
- load                 : load a context (imports resolved by storage)
- set_mandatory_tools  : replace the context's mandatory_tools list and save
- save                 : create/update a context (text and/or frontmatter data)

The handler prefers the injected ``storage`` from the FCP execution context;
otherwise it builds a JsonFileStorage from config (same as other handlers).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.storage.interfaces import ContextStore
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths

logger = logging.getLogger(__name__)

DEFAULT_LIST_LIMIT = 200


class ContextHandler(HandlerV2):
    NAME = "context_handler"

    def __init__(self, config: Optional[ConfigManager]):
        self.config = config
        self.storage: Optional[ContextStore] = self._build_storage(config)

    # ------------------------------------------------------------------
    # HandlerV2 contract
    # ------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Manage conversation contexts (whiteboards). List contexts, "
                "load a context and resolve its skill imports, update the "
                "mandatory_tools list, or save a context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "load", "set_mandatory_tools", "save"],
                        "description": "Which context operation to perform.",
                    },
                    "context_name": {
                        "type": "string",
                        "description": (
                            "Context name (file stem). Required for load, "
                            "set_mandatory_tools, and save. If omitted for load "
                            "or set_mandatory_tools, the active request context "
                            "is used."
                        ),
                    },
                    "tool_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of tool handler names. Used by "
                            "set_mandatory_tools; replaces the context's "
                            "mandatory_tools frontmatter entry."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": "New context body text. Used by save.",
                    },
                    "data": {
                        "type": "object",
                        "description": (
                            "Additional frontmatter key/value pairs to merge "
                            "into the context on save (e.g. tag, imports, "
                            "allowed_tools)."
                        ),
                        "additionalProperties": True,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max context names to return for list.",
                        "default": DEFAULT_LIST_LIMIT,
                    },
                },
                "required": ["action"],
            },
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "context_name": {"type": "string"},
                "context_names": {"type": "array", "items": {"type": "string"}},
                "data": {"type": "object"},
                "skills": {"type": "array"},
                "missing_skills": {"type": "array", "items": {"type": "string"}},
                "resolved_text": {"type": "string"},
                "mandatory_tools": {"type": "array", "items": {"type": "string"}},
                "required_tools": {"type": "array", "items": {"type": "string"}},
                "error": {"type": "object"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:
        action = str(args.get("action") or "").strip().lower()

        logger.info("context_handler input account=%s action=%s", account_name, action)

        valid_actions = {"list", "load", "set_mandatory_tools", "save"}
        if action not in valid_actions:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {"code": "invalid_action", "message": f"Unknown action: {action}"},
            }

        try:
            if action == "list":
                return self._handle_list(account_name, args)
            elif action == "load":
                return self._handle_load(account_name, args, context)
            elif action == "set_mandatory_tools":
                return self._handle_set_mandatory_tools(account_name, args, context)
            elif action == "save":
                return self._handle_save(account_name, args, context)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("context_handler failed action=%s", action)
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {"code": "internal_error", "message": f"{type(exc).__name__}: {exc}"},
            }

        return {"ok": False, "tool": self.NAME, "error": {"code": "unknown", "message": "Unhandled code path"}}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_storage(self, context: Dict[str, Any]) -> Optional[ContextStore]:
        storage = context.get("storage")
        if storage is not None:
            return storage
        return self.storage

    @staticmethod
    def _build_storage(config: Optional[ConfigManager]):
        if config is None:
            return None
        try:
            storage_root = config.get("storage_root_path")
            storage_ns = config.get("storage_namespace")
            if storage_root:
                sp = StoragePaths(storage_root, storage_ns)
                return JsonFileStorage(sp)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("context_handler: failed to build storage from config: %s", exc)
        return None

    @staticmethod
    def _resolve_account_name(account_name: str, context: Dict[str, Any]) -> str:
        if account_name and account_name != "auto":
            return account_name
        value = context.get("account_name")
        if value:
            return str(value)
        account = context.get("account")
        if isinstance(account, dict):
            for key in ("account_name", "name", "id"):
                value = account.get(key)
                if value:
                    return str(value)
        return account_name

    @staticmethod
    def _resolve_context_name(args: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        name = args.get("context_name")
        if name:
            return str(name).strip()

        name = context.get("context_name")
        if name and name != "none":
            return str(name).strip()

        cs = context.get("context_state")
        if cs is not None:
            cid = getattr(cs, "id", None)
            if cid:
                return str(cid)
        return None

    def _require_context_name(self, args: Dict[str, Any], context: Dict[str, Any], action: str):
        name = self._resolve_context_name(args, context)
        if not name:
            return None, {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": {"code": "missing_context_name", "message": "context_name is required"},
            }
        return name, None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _handle_list(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        account = self._resolve_account_name(account_name, {})
        storage = self.storage
        if storage is None:
            return {"ok": False, "tool": self.NAME, "action": "list",
                    "error": {"code": "no_storage", "message": "No storage available"}}

        names = storage.list_context_names(account)
        try:
            limit = int(args.get("limit") or DEFAULT_LIST_LIMIT)
        except (TypeError, ValueError):
            limit = DEFAULT_LIST_LIMIT
        names = names[:limit]

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "list",
            "account_name": account,
            "context_names": names,
            "count": len(names),
        }

    def _handle_load(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        name, err = self._require_context_name(args, context, "load")
        if err:
            return err
        account = self._resolve_account_name(account_name, context)
        storage = self._get_storage(context)
        if storage is None:
            return {"ok": False, "tool": self.NAME, "action": "load",
                    "error": {"code": "no_storage", "message": "No storage available"}}

        ctx = storage.get_context(account, name)
        if ctx is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "load",
                "context_name": name,
                "error": {"code": "not_found", "message": f"context '{name}' not found"},
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "load",
            "context_name": name,
            "account_name": account,
            "data": ctx.to_data(),
            "skills": [s.name for s in ctx.resolved_skills],
            "missing_skills": list(ctx.missing_imports),
            "resolved_text": ctx.resolved_text,
            "mandatory_tools": list(ctx.mandatory_tools),
            "required_tools": ctx.required_tools,
        }

    def _handle_set_mandatory_tools(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        name, err = self._require_context_name(args, context, "set_mandatory_tools")
        if err:
            return err

        raw = args.get("tool_names")
        if not isinstance(raw, list):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "set_mandatory_tools",
                "context_name": name,
                "error": {"code": "invalid_tool_names", "message": "tool_names must be a list of tool handler names"},
            }

        tool_names: List[str] = []
        for item in raw:
            s = str(item).strip()
            if s and s not in tool_names:
                tool_names.append(s)

        account = self._resolve_account_name(account_name, context)
        storage = self._get_storage(context)
        if storage is None:
            return {"ok": False, "tool": self.NAME, "action": "set_mandatory_tools",
                    "error": {"code": "no_storage", "message": "No storage available"}}

        ctx = storage.get_or_create_context(account, name)
        ctx.mandatory_tools = tool_names
        storage.save_context(ctx)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "set_mandatory_tools",
            "context_name": name,
            "account_name": account,
            "mandatory_tools": tool_names,
        }

    def _handle_save(self, account_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        name, err = self._require_context_name(args, context, "save")
        if err:
            return err

        account = self._resolve_account_name(account_name, context)
        storage = self._get_storage(context)
        if storage is None:
            return {"ok": False, "tool": self.NAME, "action": "save",
                    "error": {"code": "no_storage", "message": "No storage available"}}

        ctx = storage.get_or_create_context(account, name)

        if "text" in args and args["text"] is not None:
            ctx.text = str(args["text"])

        data = args.get("data")
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "text":
                    ctx.text = str(value) if value is not None else ""
                elif key == "tag":
                    if isinstance(value, str):
                        ctx.tag = value
                    else:
                        ctx.extra[key] = value
                elif key in ("imports", "mandatory_tools", "search_namespaces"):
                    if isinstance(value, list):
                        setattr(ctx, key, [v for v in value if isinstance(v, str)])
                    else:
                        ctx.extra[key] = value
                elif key == "updated_at" and isinstance(value, str):
                    try:
                        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        ctx.updated_at = parsed
                    except Exception:
                        ctx.extra[key] = value
                else:
                    ctx.extra[key] = value

        storage.save_context(ctx)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "save",
            "context_name": name,
            "account_name": account,
            "data": ctx.to_data(),
        }

