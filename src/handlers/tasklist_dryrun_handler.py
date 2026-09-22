"""Read-only dry-run handler for persisted tasklists."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.config_manager import ConfigManager
from src.handlers.delegate_task_handler import DelegateTaskHandler
from src.handlers.handler_v2 import HandlerV2
from src.storage.json_file_storage import JsonFileStorage
from src.storage.json_file_storage_parts.tasklists import DEFAULT_RUN_TTL_DAYS
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.service import TaskListService

logger = logging.getLogger(__name__)


class TasklistDryrunHandler(HandlerV2):
    NAME = "tasklist_dryrun"
    DRYRUN_AGENT = "colin"
    DRYRUN_CONTEXT = "dry-run-task"

    def __init__(
        self,
        config: ConfigManager,
        delegate_handler: Optional[DelegateTaskHandler] = None,
    ):
        self.config = config
        storage_root = self.config.get("storage_root_path")
        storage_ns = self.config.get("storage_namespace")
        sp = StoragePaths(storage_root, storage_ns)
        ttl_days = (self.config.get("tasklists", {}) or {}).get(
            "run_ttl_days", DEFAULT_RUN_TTL_DAYS
        )
        store = JsonFileStorage(sp, tasklist_run_ttl_days=ttl_days)
        self.tasklist_service = TaskListService(store)
        self.delegate_handler = delegate_handler or DelegateTaskHandler(config)

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Load a persisted tasklist without modifying it and dry-run each "
                "task through the configured dry-run worker context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasklist_id": {
                        "type": "string",
                        "description": "ID of the persisted tasklist to inspect.",
                    }
                },
                "required": ["tasklist_id"],
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
                "tasklist_id": {"type": "string"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "state": {"type": "string"},
                            "instructions": {"type": "string"},
                            "dry_run": {"type": "object"},
                        },
                        "required": [
                            "id",
                            "name",
                            "state",
                            "instructions",
                            "dry_run",
                        ],
                        "additionalProperties": False,
                    },
                },
                "error": {"type": "object"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context,
    ) -> Dict[str, Any]:
        tasklist_id = (args.get("tasklist_id") or "").strip()
        correlation_id = context.get("correlation_id")

        if not tasklist_id:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {
                    "code": "missing_tasklist_id",
                    "message": "tasklist_id is required.",
                },
            }

        logger.info(
            "tasklist_dryrun start account=%s tasklist_id=%s correlation_id=%s",
            account_name,
            tasklist_id,
            correlation_id,
        )
        try:
            tasklist = self.tasklist_service.get(account_name, tasklist_id)
            if tasklist is None:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "tasklist_id": tasklist_id,
                    "error": {
                        "code": "tasklist_not_found",
                        "message": f"tasklist '{tasklist_id}' not found",
                    },
                }

            tasks = []
            for task in tasklist.tasks:
                dry_run = self.delegate_handler.execute(
                    {
                        "task": task.instructions,
                        "agentName": self.DRYRUN_AGENT,
                        "capabilities": [],
                        "project": "",
                        "machine": "",
                        "contextName": self.DRYRUN_CONTEXT,
                        "accountName": account_name,
                        "timeout_seconds": self.delegate_handler.DEFAULT_TIMEOUT,
                    },
                    account_name=account_name,
                )
                tasks.append(
                    {
                        "id": task.id,
                        "name": task.name,
                        "state": task.state,
                        "instructions": task.instructions,
                        "dry_run": dry_run,
                    }
                )

            return {
                "ok": True,
                "tool": self.NAME,
                "tasklist_id": tasklist_id,
                "tasks": tasks,
            }
        except Exception as exc:
            logger.exception("tasklist_dryrun failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "tasklist_id": tasklist_id,
                "error": {"code": "internal_error", "message": str(exc)},
            }
        finally:
            logger.info(
                "tasklist_dryrun end account=%s tasklist_id=%s correlation_id=%s",
                account_name,
                tasklist_id,
                correlation_id,
            )
