from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_LIST_STATE_CREATED, TASK_STATE_PENDING

logger = logging.getLogger(__name__)


class TasklistsManageHandler(HandlerV2):
    NAME = "tasklists_manage"

    def __init__(self, config: ConfigManager):
        self.config = config
        storage_root = self.config.get("storage_root_path")
        storage_ns = self.config.get("storage_namespace")
        sp = StoragePaths(storage_root, storage_ns)
        self.storage = JsonFileStorage(sp)

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Manage persisted tasklists: list/get/put/delete/reset, plus per-action task and metadata operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list", "get", "put", "delete", "reset",
                            "add_task", "update_task", "remove_task",
                            "set_state", "set_name", "set_description",
                            "set_general_instructions", "update_meta",
                        ],
                    },
                    # --- common params ---
                    "tasklist_key": {
                        "type": "string",
                        "description": "Tasklist filename key. Required for all actions except 'list'.",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, validate but do not persist.",
                        "default": False,
                    },
                    # --- put: convenience path (use when 'goal' is present) ---
                    "goal": {
                        "type": "string",
                        "description": "Short goal. Becomes name, description, and general_instructions. Use for convenience creation.",
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File paths. One task per file. Only used with 'goal' (convenience path).",
                    },
                    "worker_agent": {
                        "type": "string",
                        "description": "Worker agent name. Sets task.agent on every auto-generated task. Only used with 'goal'.",
                    },
                    # --- put: explicit path (use when 'goal' is absent) ---
                    "name": {
                        "type": "string",
                        "description": "Human-readable tasklist name. Required for explicit put, or the new name for set_name.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What this tasklist is for. Required for explicit put, or the new description for set_description.",
                    },
                    "general_instructions": {
                        "type": "string",
                        "description": "Cross-cutting context for all tasks. Used by put explicit path.",
                    },
                    # --- add_task ---
                    "task_id": {
                        "type": "string",
                        "description": "Unique task identifier. Required for add_task, update_task, remove_task.",
                    },
                    "task_name": {
                        "type": "string",
                        "description": "Short goal name for the task. Used by add_task, update_task.",
                    },
                    "task_instructions": {
                        "type": "string",
                        "description": "Detailed instructions for the task. Used by add_task, update_task.",
                    },
                    "after_index": {
                        "type": "integer",
                        "description": "Insert after this position (0-based). Omit to append. Used by add_task.",
                    },
                    "task_state": {
                        "type": "string",
                        "description": "Task state. Default 'Pending'. Used by add_task, update_task.",
                    },
                    "task_agent": {
                        "type": "string",
                        "description": "Worker agent name for this task. Used by add_task, update_task.",
                    },
                    "task_meta": {
                        "type": "object",
                        "description": "Key-value context for the task. Merged into existing meta on update_task.",
                        "additionalProperties": False,
                    },
                    # --- update_task specific ---
                    "task_result": {
                        "type": "object",
                        "description": "New result for the task. Used by update_task.",
                        "additionalProperties": False,
                    },
                    "task_error": {
                        "type": "string",
                        "description": "New error for the task. Used by update_task.",
                    },
                    # --- set_state ---
                    "state": {
                        "type": "string",
                        "description": "New tasklist state. Required for set_state.",
                    },
                    # --- set_general_instructions ---
                    "instructions": {
                        "type": "string",
                        "description": "New general_instructions text. Required for set_general_instructions.",
                    },
                    # --- update_meta ---
                    "meta": {
                        "type": "object",
                        "description": "Key-value pairs to merge into the tasklist's meta. Required for update_meta.",
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
            "list", "get", "put", "delete", "reset",
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

    def _require_found(self, tl: TaskList | None, tasklist_key: str, action: str) -> Dict[str, Any] | None:
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

    def _load_and_require(self, account_name: str, tasklist_key: str, action: str) -> tuple[TaskList | None, Dict[str, Any] | None]:
        """Load tasklist and return (tasklist, error_or_none)."""
        err = self._require_key(tasklist_key, action)
        if err:
            return None, err
        tl = self.storage.get_tasklist(account_name, tasklist_key)
        err = self._require_found(tl, tasklist_key, action)
        return tl, err

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_list(self, account_name: str) -> Dict[str, Any]:
        ids = self.storage.list_tasklists(account_name)
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

    def _handle_delete(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        err = self._require_key(tasklist_key, "delete")
        if err:
            return err
        # delete is idempotent per storage contract
        self.storage.delete_tasklist(account_name, tasklist_key)
        return {"ok": True, "tool": self.NAME, "action": "delete", "tasklist_key": tasklist_key}

    def _handle_reset(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "reset")
        if err:
            return err

        # Work on a copy to avoid mutating the original when validate_only=True
        reset_dict = tl.to_dict()
        reset_dict["state"] = TASK_LIST_STATE_CREATED
        reset_dict["current_task_id"] = None
        for task in reset_dict["tasks"]:
            task["state"] = TASK_STATE_PENDING
            task["result"] = None
            task["error"] = None

        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, reset_dict)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "reset",
            "tasklist_key": tasklist_key,
            "tasklist": reset_dict,
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

        # Derive human-readable name from key: "fix-handler-timeout" → "Fix Handler Timeout"
        name = tasklist_key.replace("-", " ").replace("_", " ").title()

        tl = TaskList(
            id=tasklist_key,
            schema_version=1,
            state=TASK_LIST_STATE_CREATED,
            name=name,
            description=goal,
            tasks=[],
            meta={},
            general_instructions=goal,
        )

        if files:
            for i, filepath in enumerate(files):
                fname = os.path.basename(filepath)
                task_name = os.path.splitext(fname)[0]
                task = Task(
                    id=f"task-{i + 1}",
                    name=task_name,
                    instructions=goal,
                    agent=worker_agent,
                )
                tl.add_task(task)
        else:
            task = Task(
                id="task-1",
                name="Execute goal",
                instructions=goal,
                agent=worker_agent,
            )
            tl.add_task(task)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "put", "tasklist_key": tasklist_key, "tasklist": payload}

    def _put_explicit(self, account_name: str, tasklist_key: str, args: Dict[str, Any], validate_only: bool) -> Dict[str, Any]:
        name = args["name"]
        description = args["description"]
        general_instructions = args.get("general_instructions", "")

        tl = TaskList(
            id=tasklist_key,
            schema_version=1,
            state=TASK_LIST_STATE_CREATED,
            name=name,
            description=description,
            tasks=[],
            meta={},
            general_instructions=general_instructions,
        )

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "put", "tasklist_key": tasklist_key, "tasklist": payload}

    # ------------------------------------------------------------------
    # Per-action: task and metadata mutations
    # ------------------------------------------------------------------

    def _handle_add_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "add_task")
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

        task = Task(
            id=task_id,
            name=task_name,
            instructions=args.get("task_instructions", ""),
            state=args.get("task_state"),
            agent=args.get("task_agent"),
            meta=args.get("task_meta") or {},
        )

        after_index = args.get("after_index")
        if after_index is not None:
            insert_at = min(int(after_index) + 1, len(tl.tasks))
            tl.tasks.insert(insert_at, task)
        else:
            tl.tasks.append(task)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "add_task", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_update_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "update_task")
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

        # Find task
        target = tl.get_task(target_task_id)
        if target is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "update_task",
                "tasklist_key": tasklist_key,
                "error": {"code": "not_found", "message": f"task with id '{target_task_id}' not found"},
            }

        # Merge fields
        if "task_name" in args:
            target.name = str(args["task_name"])
        if "task_instructions" in args:
            target.instructions = str(args["task_instructions"])
        if "task_state" in args:
            target.state = str(args["task_state"])
        if "task_result" in args:
            target.result = args["task_result"]
        if "task_error" in args:
            target.error = args["task_error"]
        if "task_meta" in args and isinstance(args["task_meta"], dict):
            target.meta.update(args["task_meta"])
        if "task_agent" in args:
            target.agent = args["task_agent"]

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "update_task", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_remove_task(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "remove_task")
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

        for i, t in enumerate(tl.tasks):
            if str(t.id) == target_task_id:
                tl.tasks.pop(i)
                break
        else:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "remove_task",
                "tasklist_key": tasklist_key,
                "error": {"code": "not_found", "message": f"task with id '{target_task_id}' not found"},
            }

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "remove_task", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_set_state(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "set_state")
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

        tl.state = str(state)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "set_state", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_set_name(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "set_name")
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

        tl.name = str(name)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "set_name", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_set_description(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "set_description")
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

        tl.description = str(description)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "set_description", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_set_general_instructions(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "set_general_instructions")
        if err:
            return err

        instructions = args.get("instructions", "")
        tl.general_instructions = str(instructions)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "set_general_instructions", "tasklist_key": tasklist_key, "tasklist": payload}

    def _handle_update_meta(self, account_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tasklist_key = (args.get("tasklist_key") or "").strip()
        validate_only = bool(args.get("validate_only", False))
        tl, err = self._load_and_require(account_name, tasklist_key, "update_meta")
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

        tl.meta.update(meta_update)

        payload = tl.to_dict()
        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, payload)

        return {"ok": True, "tool": self.NAME, "action": "update_meta", "tasklist_key": tasklist_key, "tasklist": payload}
