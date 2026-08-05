from __future__ import annotations

import json
import logging
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
            "description": "Manage persisted tasklists: list/get/put/patch/delete/reset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "put", "patch", "delete", "reset"],
                    },
                    "tasklist_key": {
                        "type": "string",
                        "description": "Tasklist name (simple filename).",
                        "default": "",
                    },
                    "tasklist": {
                        "type": "string",
                        "description": (
                            "Tasklist JSON payload as a string (for put/patch). "
                            "Required top-level keys: schema_version (int, always 1), "
                            "id (string UUID), name (string), description (string), "
                            "tasks (array of task objects, can be empty). "
                            "Each task REQUIRES: id (string), name (string), instructions (string). "
                            "Optional top-level: state (string, default 'created'), "
                            "meta (object), current_task_id (string|null), "
                            "general_instructions (string). "
                            "Optional per-task: state (string, default 'pending'), "
                            "result (object|null), error (string|null), "
                            "meta (object), agent (string|null). "
                            "No extra keys allowed — strict schema rejects unknown fields."
                        ),
                        "default": "",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, validate but do not persist.",
                        "default": False,
                    },
                },
                "required": ["action", "tasklist_key", "tasklist", "validate_only"],
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
                "tasklist_key": {"type": "string"},
                "tasklist": {"type": "object"},
                "tasklist_keys": {"type": "array", "items": {"type": "string"}},
                "error": {"type": "object"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:
        action = (args.get("action") or "").strip().lower()
        tasklist_key = (args.get("tasklist_key") or "").strip()
        payload = args.get("tasklist") or {}
        validate_only = bool(args.get("validate_only", False))

        logger.info(
            "tasklists.manage input account=%s action=%s id=%s validate_only=%s",
            account_name,
            action,
            tasklist_key,
            validate_only,
        )

        if action not in ("list", "get", "put", "patch", "delete", "reset"):
            return {
                "ok": False,
                "tool": self.NAME,
                "error": {"code": "invalid_action", "message": f"Unknown action: {action}"},
            }

        try:
            if action == "list":
                ids = self.storage.list_tasklists(account_name)
                return {"ok": True, "tool": self.NAME, "action": "list", "tasklist_keys": ids}

            if action == "get":
                if not tasklist_key:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "get",
                        "error": {"code": "missing_key", "message": "tasklist_key is required for get"},
                    }
                tl = self.storage.get_tasklist(account_name, tasklist_key)
                if tl is None:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "get",
                        "tasklist_key": tasklist_key,
                        "error": {"code": "not_found", "message": "tasklist not found"},
                    }
                return {
                    "ok": True,
                    "tool": self.NAME,
                    "action": "get",
                    "tasklist_key": tasklist_key,
                    "tasklist": tl.to_dict() if hasattr(tl, "to_dict") else tl,
                }

            if action == "delete":
                if not tasklist_key:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "delete",
                        "error": {"code": "missing_key", "message": "tasklist_key is required for delete"},
                    }
                # delete is idempotent per storage contract
                self.storage.delete_tasklist(account_name, tasklist_key)
                return {"ok": True, "tool": self.NAME, "action": "delete", "tasklist_key": tasklist_key}

            if action == "reset":
                if not tasklist_key:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "reset",
                        "error": {"code": "missing_key", "message": "tasklist_key is required for reset"},
                    }
                tl = self.storage.get_tasklist(account_name, tasklist_key)
                if tl is None:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "reset",
                        "tasklist_key": tasklist_key,
                        "error": {"code": "not_found", "message": "tasklist not found"},
                    }

                # Build reset state from a dict copy — never mutate the original in-place
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

            if action == "put":
                if not tasklist_key:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "put",
                        "error": {"code": "missing_key", "message": "tasklist_key is required for put"},
                    }

                # Accept JSON string or dict
                if isinstance(payload, str):
                    try:
                        payload_obj = json.loads(payload)
                        payload = payload_obj
                    except Exception:
                        return {
                            "ok": False,
                            "tool": self.NAME,
                            "action": "put",
                            "tasklist_key": tasklist_key,
                            "error": {"code": "invalid_payload", "message": "tasklist is not valid JSON"},
                        }

                # Validate payload shape by constructing a TaskList (will raise on invalid)
                try:
                    TaskList.from_dict(payload)
                except Exception as e:
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "action": "put",
                        "tasklist_key": tasklist_key,
                        "error": {"code": "invalid_tasklist", "message": str(e)},
                    }


                # Safety: if replacing an existing tasklist, require id match.
                # The URL tasklist_key is a storage key (filename), not the TaskList UUID.
                existing = self.storage.get_tasklist(account_name, tasklist_key)
                if existing is not None:
                    incoming_id = payload.get("id") if isinstance(payload, dict) else None
                    if not incoming_id:
                        return {
                            "ok": False,
                            "tool": self.NAME,
                            "action": "put",
                            "tasklist_key": tasklist_key,
                            "error": {
                                "code": "missing_tasklist_uuid",
                                "message": "TaskList.id is required when replacing an existing tasklist",
                            },
                        }
                    if incoming_id != existing.id:
                        return {
                            "ok": False,
                            "tool": self.NAME,
                            "action": "put",
                            "tasklist_key": tasklist_key,
                            "error": {
                                "code": "tasklist_uuid_mismatch",
                                "message": "TaskList.id does not match the existing stored tasklist",
                            },
                        }

                if not validate_only:
                    self.storage.save_tasklist(account_name, tasklist_key, payload)

                return {
                    "ok": True,
                    "tool": self.NAME,
                    "action": "put",
                    "tasklist_key": tasklist_key,
                    "tasklist": payload,
                }

            if action == "patch":
                return self._handle_patch(account_name, tasklist_key, payload, validate_only)

        except Exception as e:
            logger.exception("tasklists.manage failed")
            return {"ok": False, "tool": self.NAME, "error": {"code": "internal_error", "message": str(e)}}

        # fallback
        return {"ok": False, "tool": self.NAME, "error": {"code": "unknown", "message": "Unhandled code path"}}

    # ------------------------------------------------------------------
    # Patch action
    # ------------------------------------------------------------------

    def _handle_patch(
        self,
        account_name: str,
        tasklist_key: str,
        payload: Any,
        validate_only: bool,
    ) -> Dict[str, Any]:
        """Apply partial updates to an existing tasklist.

        The payload is a JSON string or dict containing an ``operations`` list.
        Each operation is a dict with an ``op`` field and operation-specific fields.

        Supported operations:

        ``add_task``
            Add a new task. Fields: ``task`` (dict with Task fields), ``after_index`` (int, optional).
            If ``after_index`` is omitted, the task is appended at the end.

        ``update_task``
            Update fields on an existing task found by ``task_id``.
            Fields: ``task_id`` (str), ``task`` (dict with Task fields to merge).

        ``remove_task``
            Remove a task by ``task_id``. Fields: ``task_id`` (str).

        ``set_state``
            Set the tasklist's ``state``. Fields: ``state`` (str).

        ``update_meta``
            Merge keys into the tasklist's ``meta`` dict. Fields: ``meta`` (dict).

        ``set_general_instructions``
            Replace the tasklist's ``general_instructions``. Fields: ``instructions`` (str).

        ``set_name``
            Replace the tasklist's ``name``. Fields: ``name`` (str).

        ``set_description``
            Replace the tasklist's ``description``. Fields: ``description`` (str).
        """
        if not tasklist_key:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "patch",
                "error": {"code": "missing_key", "message": "tasklist_key is required for patch"},
            }

        # Parse payload if it's a JSON string
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "action": "patch",
                    "tasklist_key": tasklist_key,
                    "error": {"code": "invalid_payload", "message": "payload is not valid JSON"},
                }

        if not isinstance(payload, dict):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "patch",
                "tasklist_key": tasklist_key,
                "error": {"code": "invalid_payload", "message": "payload must be a JSON object with an 'operations' list"},
            }

        operations = payload.get("operations", [])
        if not isinstance(operations, list):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "patch",
                "tasklist_key": tasklist_key,
                "error": {"code": "invalid_operations", "message": "'operations' must be a list"},
            }

        if not operations:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "patch",
                "tasklist_key": tasklist_key,
                "error": {"code": "empty_operations", "message": "at least one operation is required"},
            }

        # Load the existing tasklist
        tl = self.storage.get_tasklist(account_name, tasklist_key)
        if tl is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "patch",
                "tasklist_key": tasklist_key,
                "error": {"code": "not_found", "message": "tasklist not found"},
            }

        # Work on a copy to avoid mutating the original when validate_only=True
        tl_copy = TaskList.from_dict(tl.to_dict())

        # Apply each operation in order
        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "action": "patch",
                    "tasklist_key": tasklist_key,
                    "error": {
                        "code": "invalid_operation",
                        "message": f"operation at index {i} is not a dict",
                    },
                }

            op_type = op.get("op", "")
            try:
                self._apply_operation(tl_copy, op_type, op, i)
            except (ValueError, TypeError, IndexError, KeyError) as e:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "action": "patch",
                    "tasklist_key": tasklist_key,
                    "error": {
                        "code": "operation_failed",
                        "message": f"operation {i} ('{op_type}') failed: {e}",
                    },
                }

        if not validate_only:
            self.storage.save_tasklist(account_name, tasklist_key, tl_copy.to_dict())

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "patch",
            "tasklist_key": tasklist_key,
            "tasklist": tl_copy.to_dict(),
        }

    def _apply_operation(self, tl: TaskList, op_type: str, op: Dict[str, Any], index: int) -> None:
        """Apply a single patch operation to *tl* in place."""
        if op_type == "add_task":
            task_dict = op.get("task")
            if not isinstance(task_dict, dict):
                raise ValueError("'task' must be a dict")
            task = Task.from_dict(task_dict)
            after_index = op.get("after_index")
            if after_index is not None:
                insert_at = min(int(after_index) + 1, len(tl.tasks))
                tl.tasks.insert(insert_at, task)
            else:
                tl.tasks.append(task)

        elif op_type == "update_task":
            task_id = str(op.get("task_id", ""))
            if not task_id:
                raise ValueError("'task_id' is required for update_task")
            task_dict = op.get("task", {})
            if not isinstance(task_dict, dict):
                raise ValueError("'task' must be a dict")
            # Find task by ID
            target = None
            for t in tl.tasks:
                if str(t.id) == task_id:
                    target = t
                    break
            if target is None:
                raise ValueError(f"task with id '{task_id}' not found")
            # Merge fields from task_dict into the existing Task
            if "id" in task_dict:
                target.id = str(task_dict["id"])
            if "name" in task_dict:
                target.name = str(task_dict["name"])
            if "instructions" in task_dict:
                target.instructions = str(task_dict["instructions"])
            if "state" in task_dict:
                target.state = str(task_dict["state"])
            if "result" in task_dict:
                target.result = task_dict["result"]
            if "error" in task_dict:
                target.error = task_dict["error"]
            if "meta" in task_dict and isinstance(task_dict["meta"], dict):
                target.meta.update(task_dict["meta"])

        elif op_type == "remove_task":
            task_id = str(op.get("task_id", ""))
            if not task_id:
                raise ValueError("'task_id' is required for remove_task")
            # Find and remove task by ID
            for i, t in enumerate(tl.tasks):
                if str(t.id) == task_id:
                    tl.tasks.pop(i)
                    return
            raise ValueError(f"task with id '{task_id}' not found")

        elif op_type == "set_state":
            state = op.get("state", "")
            if not state:
                raise ValueError("'state' is required for set_state")
            tl.state = str(state)

        elif op_type == "update_meta":
            meta_update = op.get("meta", {})
            if not isinstance(meta_update, dict):
                raise ValueError("'meta' must be a dict")
            tl.meta.update(meta_update)

        elif op_type == "set_general_instructions":
            instructions = op.get("instructions", "")
            tl.general_instructions = str(instructions)

        elif op_type == "set_name":
            name = op.get("name", "")
            if not name:
                raise ValueError("'name' is required for set_name")
            tl.name = str(name)

        elif op_type == "set_description":
            description = op.get("description", "")
            if not description:
                raise ValueError("'description' is required for set_description")
            tl.description = str(description)

        else:
            raise ValueError(f"unknown operation '{op_type}'")
