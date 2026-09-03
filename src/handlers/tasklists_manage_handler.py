from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.storage.json_file_storage import JsonFileStorage
from src.storage.json_file_storage_parts.tasklists import DEFAULT_RUN_TTL_DAYS
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.service import TaskListService

logger = logging.getLogger(__name__)


class TasklistsManageHandler(HandlerV2):
    NAME = "tasklists_manage"

    def __init__(self, config: ConfigManager):
        self.config = config
        storage_root = self.config.get("storage_root_path")
        storage_ns = self.config.get("storage_namespace")
        sp = StoragePaths(storage_root, storage_ns)
        ttl_days = (self.config.get("tasklists", {}) or {}).get("run_ttl_days", DEFAULT_RUN_TTL_DAYS)
        store = JsonFileStorage(sp, tasklist_run_ttl_days=ttl_days)
        self.tasklist_service = TaskListService(store)

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Manage tasklists and tasks: list/get/put/delete/reset plus per-task and meta updates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list", "get", "get_result", "put", "delete", "reset",
                            "add_task", "update_task", "remove_task",
                            "set_state", "set_name", "set_description",
                            "set_general_instructions", "update_meta",
                        ],
                    },
                    "tasklist_key": {
                        "type": "string",
                        "description": "Tasklist filename key. Required except for 'list'.",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, validate without persisting.",
                        "default": False,
                    },
                    "goal": {
                        "type": "string",
                        "description": "Short goal; becomes name+description+instructions.",
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One task per file. Used with 'goal'.",
                    },
                    "worker_agent": {
                        "type": "string",
                        "description": "Worker agent for auto-tasks. Used with 'goal'.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Tasklist name (put) or new name (set_name).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Tasklist description (put) or new value (set_description).",
                    },
                    "general_instructions": {
                        "type": "string",
                        "description": "Cross-cutting instructions (put).",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Task id (add/update/remove_task/get_result).",
                    },
                    "task_name": {
                        "type": "string",
                        "description": "Task name (add/update_task).",
                    },
                    "task_instructions": {
                        "type": "string",
                        "description": "Task instructions (add/update_task).",
                    },
                    "after_index": {
                        "type": "integer",
                        "description": "Insert after 0-based index; omit to append (add_task).",
                    },
                    "task_state": {
                        "type": "string",
                        "description": "Task state (default Pending).",
                    },
                    "task_agent": {
                        "type": "string",
                        "description": "Task worker agent.",
                    },
                    "task_meta": {
                        "type": "object",
                        "description": "Task meta; merged on update.",
                        "additionalProperties": False,
                    },
                    "task_position": {
                        "type": ["integer", "null"],
                        "description": "Task position (null=append).",
                    },
                    "task_parent_id": {
                        "type": ["string", "null"],
                        "description": "Parent task id.",
                    },
                    "task_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Task file paths.",
                    },
                    "task_result": {
                        "type": "object",
                        "description": "New task result.",
                        "additionalProperties": False,
                    },
                    "task_error": {
                        "type": "string",
                        "description": "New task error.",
                    },
                    "state": {
                        "type": "string",
                        "description": "New tasklist state (set_state).",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "New general_instructions (set_general_instructions).",
                    },
                    "meta": {
                        "type": "object",
                        "description": "Meta to merge (update_meta).",
                        "additionalProperties": False,
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "tasklist_key": {"type": "string"},
                "tasklist": {"type": "object"},
                "tasklist_keys": {"type": "array", "items": {"type": "string"}},
                "error": {"type": "object"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:
        action = (args.get("action") or "").strip().lower()

        logger.info(
            "tasklists.manage input account=%s action=%s",
            account_name,
            action,
        )

        valid_actions = {
            "list", "get", "get_result", "put", "delete", "reset",
            "add_task", "update_task", "remove_task",
            "set_state", "set_name", "set_description",
            "set_general_instructions", "update_meta",
        }

        if action not in valid_actions:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {"code": "invalid_action", "message": f"Unknown action: {action}"},
            }

        try:
            if action == "list":
                return self._handle_list(account_name)
            elif action == "get":
                return self._handle_get(account_name, args)
            elif action == "get_result":
                return self._handle_get_result(account_name, args)
            elif action == "put":
                return self._handle_put(account_name, args)
            elif action == "delete":
                return self._handle_delete(account_name, args)
            elif action == "reset":
                return self._handle_reset(account_name, args)
            elif action == "add_task":
                return self._handle_add_task(account_name, args)
            elif action == "update_task":
                return self._handle_update_task(account_name, args)
            elif action == "remove_task":
                return self._handle_remove_task(account_name, args)
            elif action == "set_state":
                return self._handle_set_state(account_name, args)
            elif action == "set_name":
                return self._handle_set_name(account_name, args)
            elif action == "set_description":
                return self._handle_set_description(account_name, args)
            elif action == "set_general_instructions":
                return self._handle_set_general_instructions(account_name, args)
            elif action == "update_meta":
                return self._handle_update_meta(account_name, args)

        except Exception as e:
            logger.exception("tasklists.manage failed")
            return {"ok": False, "tool": self.NAME, "error": {"code": "internal_error", "message": str(e)}}

        return {"ok": False, "tool": self.NAME, "error": {"code": "unknown", "message": "Unhandled code path"}}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_key(tasklist_key: str, action: str) -> Dict[str, Any] | None:
        """Return an error dict if tasklist_key is missing, else None."""
        if not tasklist_key:
            return {
                "ok": False,
                "tool": "tasklists_manage",
                "action": action,
                "error": {"code": "missing_key", "message": "tasklist_key is required"},
            }
        return None

    def _require_found(self, tl, tasklist_key: str, action: str) -> Dict[str, Any] | None:
        """Return an error dict if tasklist is None, else None."""
        if tl is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "tasklist_key": tasklist_key,
                "error": {"code": "not_found", "message": "tasklist not found"},
            }
        return None

    def _load_and_require(self, account_name: str, tasklist_key: str, action: str):
        """Load tasklist and return (tasklist, error_or_none)."""
        err = self._require_key(tasklist_key, action)
        if err:
            return None, err
        tl = self.tasklist_service.get(account_name, tasklist_key)
        err = self._require_found(tl, tasklist_key, action)
        return tl, err

    def _service_error(self, exc: ValueError, action: str, tasklist_key: str) -> Dict[str, Any] | None:
        message = str(exc)
        if "not found" in message:
            code = "not_found"
        elif "already exists" in message:
            code = "duplicate_task_id"
        else:
            return None
        return {
            "ok": False,
            "tool": self.NAME,
            "action": action,
            "tasklist_key": tasklist_key,
            "error": {"code": code, "message": message},
        }

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_list(self, account_name: str) -> Dict[str, Any]:
        ids = self.tasklist_service.list(account_name)
        return {"ok": True, "tool": self.NAME, "action": "list", "tasklist_keys": ids}

    def _handle_get(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        tl, err = self._load_and_require(account_name, tasklist_key, "get")
        if err:
            return err
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "get",
            "tasklist_key": tasklist_key,
            "tasklist": tl.to_dict(),
        }

    def _handle_get_result(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        err = self._require_key(tasklist_key, "get_result")
        if err:
            return err

        task_id = str(args.get("task_id") or "").strip()
        if not task_id:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "get_result",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "task_id is required for get_result"},
            }

        record = self.tasklist_service.get_task_result(account_name, tasklist_key, task_id)
        if record is not None:
            return {
                "ok": True,
                "tool": self.NAME,
                "action": "get_result",
                "tasklist_key": tasklist_key,
                "task_id": task_id,
                "result_record": record,
            }
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "get_result",
            "tasklist_key": tasklist_key,
            "task_id": task_id,
            "message": f"no result for task {task_id}",
        }

    def _handle_delete(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        err = self._require_key(tasklist_key, "delete")
        if err:
            return err
        # delete is idempotent per storage contract
        self.tasklist_service.delete(account_name, tasklist_key)
        return {"ok": True, "tool": self.NAME, "action": "delete", "tasklist_key": tasklist_key}

    def _handle_reset(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "reset")
        if err:
            return err

        self.tasklist_service.reset(tl)
        if not validate_only:
            self.tasklist_service.save(account_name, tasklist_key, tl)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "reset",
            "tasklist_key": tasklist_key,
            "tasklist": tl.to_dict(),
        }

    # ------------------------------------------------------------------
    # _handle_put — convenience / explicit
    # ------------------------------------------------------------------

    def _handle_put(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "put")
        if err:
            return err

        # Convenience path: goal provided
        if "goal" in args and args["goal"]:
            return self._put_convenience(account_name, tasklist_key, args, validate_only)

        # Explicit path: name + description provided
        if "name" in args and args.get("name") and "description" in args and args.get("description"):
            return self._put_explicit(account_name, tasklist_key, args, validate_only)

        return {
            "ok": False,
            "tool": self.NAME,
            "action": "put",
            "tasklist_key": tasklist_key,
            "error": {"code": "missing_fields", "message": "must provide 'goal' or ('name' + 'description')"},
        }

    def _put_convenience(self, account_name: str, tasklist_key: str, args: Dict[str, Any], validate_only: bool) -> Dict[str, Any]:
        goal = args["goal"]
        files = args.get("files") or []
        worker_agent = args.get("worker_agent")

        tl = self.tasklist_service.create_from_goal(tasklist_key, goal, files, worker_agent)
        if not validate_only:
            self.tasklist_service.save(account_name, tasklist_key, tl)

        return {"ok": True, "tool": self.NAME, "action": "put", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _put_explicit(self, account_name: str, tasklist_key: str, args: Dict[str, Any], validate_only: bool) -> Dict[str, Any]:
        name = args["name"]
        description = args["description"]
        general_instructions = args.get("general_instructions", "")

        tl = self.tasklist_service.create(tasklist_key, name, description, general_instructions=general_instructions)
        if not validate_only:
            self.tasklist_service.save(account_name, tasklist_key, tl)

        return {"ok": True, "tool": self.NAME, "action": "put", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    # ------------------------------------------------------------------
    # Per-action: task and metadata mutations
    # ------------------------------------------------------------------

    def _handle_add_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "add_task")
        if err:
            return err

        task_id = args.get("task_id", "")
        task_name = args.get("task_name", "")
        if not task_id or not task_name:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "add_task",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "task_id and task_name are required for add_task"},
            }

        try:
            tl = self.tasklist_service.add_task(
                account_name,
                tasklist_key,
                task_id=task_id,
                task_name=task_name,
                task_instructions=args.get("task_instructions", ""),
                task_state=args.get("task_state"),
                task_agent=args.get("task_agent"),
                task_meta=args.get("task_meta"),
                task_position=args.get("task_position"),
                task_parent_id=args.get("task_parent_id"),
                task_files=args.get("task_files"),
                after_index=args.get("after_index"),
                validate_only=validate_only,
            )
        except ValueError as e:
            err = self._service_error(e, "add_task", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "add_task", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_update_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "update_task")
        if err:
            return err

        target_task_id = str(args.get("task_id", ""))
        if not target_task_id:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "update_task",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "task_id is required for update_task"},
            }

        changes: Dict[str, Any] = {}
        if "task_name" in args:
            changes["name"] = args["task_name"]
        if "task_instructions" in args:
            changes["instructions"] = args["task_instructions"]
        if "task_state" in args:
            changes["state"] = args["task_state"]
        if "task_error" in args:
            changes["error"] = args["task_error"]
        if "task_meta" in args and isinstance(args["task_meta"], dict):
            changes["meta"] = args["task_meta"]
        if "task_agent" in args:
            changes["agent"] = args["task_agent"]
        if "task_position" in args:
            changes["position"] = args["task_position"]
        if "task_parent_id" in args:
            changes["parent_id"] = args["task_parent_id"]
        if "task_files" in args:
            changes["files"] = args["task_files"]

        try:
            tl = self.tasklist_service.update_task(
                account_name,
                tasklist_key,
                target_task_id,
                validate_only=validate_only,
                **changes,
            )
        except ValueError as e:
            err = self._service_error(e, "update_task", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "update_task", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_remove_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "remove_task")
        if err:
            return err

        target_task_id = str(args.get("task_id", ""))
        if not target_task_id:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "remove_task",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "task_id is required for remove_task"},
            }

        try:
            tl = self.tasklist_service.remove_task(
                account_name,
                tasklist_key,
                target_task_id,
                validate_only=validate_only,
            )
        except ValueError as e:
            err = self._service_error(e, "remove_task", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "remove_task", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_set_state(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "set_state")
        if err:
            return err

        state = args.get("state", "")
        if not state:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "set_state",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "state is required for set_state"},
            }

        try:
            tl = self.tasklist_service.set_state(account_name, tasklist_key, state, validate_only=validate_only)
        except ValueError as e:
            err = self._service_error(e, "set_state", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "set_state", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_set_name(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "set_name")
        if err:
            return err

        name = args.get("name", "")
        if not name:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "set_name",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "name is required for set_name"},
            }

        try:
            tl = self.tasklist_service.set_name(account_name, tasklist_key, name, validate_only=validate_only)
        except ValueError as e:
            err = self._service_error(e, "set_name", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "set_name", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_set_description(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "set_description")
        if err:
            return err

        description = args.get("description", "")
        if not description:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "set_description",
                "tasklist_key": tasklist_key,
                "error": {"code": "missing_fields", "message": "description is required for set_description"},
            }

        try:
            tl = self.tasklist_service.set_description(account_name, tasklist_key, description, validate_only=validate_only)
        except ValueError as e:
            err = self._service_error(e, "set_description", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "set_description", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_set_general_instructions(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "set_general_instructions")
        if err:
            return err

        instructions = args.get("instructions", "")

        try:
            tl = self.tasklist_service.set_general_instructions(
                account_name,
                tasklist_key,
                instructions,
                validate_only=validate_only,
            )
        except ValueError as e:
            err = self._service_error(e, "set_general_instructions", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "set_general_instructions", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}

    def _handle_update_meta(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))

        err = self._require_key(tasklist_key, "update_meta")
        if err:
            return err

        meta_update = args.get("meta", {})
        if not isinstance(meta_update, dict):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "update_meta",
                "tasklist_key": tasklist_key,
                "error": {"code": "invalid_meta", "message": "meta must be a dict"},
            }

        try:
            tl = self.tasklist_service.update_meta(
                account_name,
                tasklist_key,
                meta_update,
                validate_only=validate_only,
            )
        except ValueError as e:
            err = self._service_error(e, "update_meta", tasklist_key)
            if err is not None:
                return err
            raise

        return {"ok": True, "tool": self.NAME, "action": "update_meta", "tasklist_key": tasklist_key, "tasklist": tl.to_dict()}
