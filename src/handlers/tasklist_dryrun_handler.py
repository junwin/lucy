"""Read-only dry-run handler for persisted tasklists."""

from __future__ import annotations

import json
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
    ASSESSMENTS = {"ready", "decompose", "blocked", "invalid"}

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
                    },
                    "agentName": {
                        "type": ["string", "null"],
                        "description": "Worker agent override; null defaults to colin.",
                    },
                    "contextName": {
                        "type": ["string", "null"],
                        "description": "Dry-run context override; null defaults to dry-run-task.",
                    },
                },
                "required": ["tasklist_id", "agentName", "contextName"],
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
                            "persisted_state": {"type": "string"},
                            "state": {
                                "type": ["string", "null"],
                                "enum": [
                                    "ready",
                                    "decompose",
                                    "blocked",
                                    "invalid",
                                    None,
                                ],
                            },
                            "intended_implementation": {"type": "string"},
                            "tests_to_add_or_run": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "error": {"type": "string"},
                        },
                        "required": [
                            "id",
                            "name",
                            "persisted_state",
                            "state",
                            "intended_implementation",
                            "tests_to_add_or_run",
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
        agent_name = (args.get("agentName") or self.DRYRUN_AGENT).strip()
        context_name = (args.get("contextName") or self.DRYRUN_CONTEXT).strip()
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
                item = {
                    "id": task.id,
                    "name": task.name,
                    "persisted_state": task.state,
                    "state": None,
                    "intended_implementation": "",
                    "tests_to_add_or_run": [],
                }
                try:
                    delegated = self.delegate_handler.execute(
                        {
                            "task": task.instructions,
                            "agentName": agent_name,
                            "capabilities": [],
                            "project": "",
                            "machine": "",
                            "contextName": context_name,
                            "accountName": account_name,
                            "timeout_seconds": self.delegate_handler.DEFAULT_TIMEOUT,
                        },
                        account_name=account_name,
                    )
                    assessment, error = self._result_from_delegate(delegated)
                    if assessment is not None:
                        item.update(assessment)
                    if error:
                        item["error"] = error
                except Exception as exc:
                    logger.exception(
                        "tasklist_dryrun task failed tasklist_id=%s task_id=%s",
                        tasklist_id,
                        task.id,
                    )
                    item["error"] = str(exc)
                tasks.append(item)

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

    @classmethod
    def _result_from_delegate(
        cls, delegated: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not delegated.get("ok"):
            error = delegated.get("error") or "delegate_task failed"
            return None, str(error)

        raw = str(delegated.get("result") or "").strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"invalid dry-run JSON: {exc.msg}"

        results = payload.get("task_results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or len(results) != 1:
            return None, "dry-run response must contain exactly one task_result"

        result = results[0]
        if not isinstance(result, dict):
            return None, "dry-run task_result must be an object"

        state = str(result.get("state") or "").strip().lower()
        if state not in cls.ASSESSMENTS:
            return None, f"unexpected dry-run state: {state!r}"

        intended = result.get("intended_implementation")
        tests = result.get("tests_to_add_or_run")
        if not isinstance(intended, str):
            return None, "dry-run intended_implementation must be a string"
        if not isinstance(tests, list) or any(not isinstance(test, str) for test in tests):
            return None, "dry-run tests_to_add_or_run must be a list of strings"

        return {
            "state": state,
            "intended_implementation": intended.strip(),
            "tests_to_add_or_run": tests,
        }, None
