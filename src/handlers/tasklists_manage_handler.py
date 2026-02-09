from __future__ import annotations

import json
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.task_list import TaskList

logger = logging.getLogger(__name__)


class TasklistsManageHandler(HandlerV2):
    NAME = "tasklists_manage"

    def __init__(self, config: ConfigManager):
        self.config = config
        # Construct storage implementation from config so handler can operate
        storage_root = self.config.get("storage_root_path")
        storage_ns = self.config.get("storage_namespace")
        sp = StoragePaths(storage_root, storage_ns)
        self.storage = JsonFileStorage(sp)

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        # NOTE: OpenAI strict tool schemas require that any nested object schema
        # explicitly sets additionalProperties: false.
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Manage persisted tasklists: list/get/put/delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "put", "delete"],
                    },
                    "tasklist_id": {
                        "type": "string",
                        "description": "Tasklist id (simple filename).",
                        "default": "",
                    },
                    "tasklist": {
                        "type": "string",
                        "description": "Tasklist payload (for put).",
                        # We accept arbitrary tasklist JSON here as a string; validation happens in code.
                        # "additionalProperties": True,
                        "default": "",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, validate but do not persist.",
                        "default": False,
                    },
                },
                "required": ["action", "tasklist_id", "tasklist", "validate_only"],
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
                "action": {"type": "string"},
                "tasklist_id": {"type": "string"},
                "tasklist": {"type": "object"},
                "tasklist_ids": {"type": "array", "items": {"type": "string"}},
                "error": {"type": "object"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        action = (args.get("action") or "").strip().lower()
        tasklist_id = (args.get("tasklist_id") or "").strip()
        payload = args.get("tasklist") or {}
        validate_only = bool(args.get("validate_only", False))

        logger.info(
            "tasklists.manage input account=%s action=%s id=%s validate_only=%s",
            account_name,
            action,
            tasklist_id,
            validate_only,
        )

        if action not in ("list", "get", "put", "delete"):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {"code": "invalid_action", "message": f"Unknown action: {action}"},
            }

        try:
            if action == "list":
                ids = self.storage.list_tasklists(account_name)
                return {"ok": True, "tool": self.NAME, "action": "list", "tasklist_ids": ids}

            if action == "get":
                if not tasklist_id:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "get",
                        "error": {"code": "missing_id", "message": "tasklist_id is required for get"},
                    }
                data = self.storage.get_tasklist(account_name, tasklist_id)
                if data is None:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "get",
                        "tasklist_id": tasklist_id,
                        "error": {"code": "not_found", "message": "tasklist not found"},
                    }
                return {
                    "ok": True,
                    "tool": self.NAME,
                    "action": "get",
                    "tasklist_id": tasklist_id,
                    "tasklist": data,
                }

            if action == "delete":
                if not tasklist_id:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "delete",
                        "error": {"code": "missing_id", "message": "tasklist_id is required for delete"},
                    }
                # delete is idempotent per storage contract
                self.storage.delete_tasklist(account_name, tasklist_id)
                return {"ok": True, "tool": self.NAME, "action": "delete", "tasklist_id": tasklist_id}

            if action == "put":
                if not tasklist_id:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "put",
                        "error": {"code": "missing_id", "message": "tasklist_id is required for put"},
                    }

                # Accept JSON string or dict
                if isinstance(payload, str):
                    try:
                        payload_obj = json.loads(payload)
                    except Exception:
                        return {
                            "ok": False,
                            "tool": self.NAME,
                            "action": "put",
                            "tasklist_id": tasklist_id,
                            "error": {"code": "invalid_payload", "message": "tasklist is not valid JSON"},
                        }
                

                

                # persist
                self.storage.save_tasklist(account_name, tasklist_id, payload)
                return {
                    "ok": True,
                    "tool": self.NAME,
                    "action": "put",
                    "tasklist_id": tasklist_id,
                    "tasklist": payload,
                }

        except Exception as e:
            logger.exception("tasklists.manage failed")
            return {"ok": False, "tool": self.NAME, "error": {"code": "internal_error", "message": str(e)}}

        # fallback
        return {"ok": False, "tool": self.NAME, "error": {"code": "unknown", "message": "Unhandled code path"}}
