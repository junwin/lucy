# src/handlers/delegate_tasks_handler.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from .handler_v2 import HandlerV2

logger = logging.getLogger(__name__)


class DelegateTasksHandler(HandlerV2):
    """Plan a simple sequential task list for a goal (and optional file list).

    Note: This handler *plans* tasks and returns a structured task list. The actual
    execution of those tasks is performed elsewhere (currently in
    `FunctionCallingProcessor`).
    """

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return "delegate_tasks"

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.name(),
            "description": (
                "Plan a simple sequential task list for a coding/refactoring goal, optionally scoped to files. "
                "Returns a structured task list that will be executed by the orchestration layer "
                "(e.g., FunctionCallingProcessor)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": (
                            "High-level description of the work to perform. "
                            "Write this as instructions for a worker agent."
                        ),
                    },
                    "files": {
                        "type": "array",
                        "description": (
                            "Optional list of file paths to focus on. If provided, "
                            "the task list will contain one task per file."
                        ),
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "instruction": {
                        "type": "string",
                        "description": (
                            "Optional detailed instruction template for each task. "
                            "If omitted, the goal will be used as the instruction."
                        ),
                        "default": "",
                    },
                    "worker_agent": {
                        "type": "string",
                        "description": (
                            "Optional name of the worker agent that should execute the tasks. "
                            "(Used for routing/documentation; execution is handled by the orchestrator.)"
                        ),
                        "default": "",
                    },
                },
                "required": ["goal", "files", "instruction", "worker_agent"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["tasklist"]},
                "description": {"type": "string"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["task"]},
                            "title": {"type": "string"},
                            "agent": {"type": "string"},
                            "instruction": {"type": "string"},
                            "file": {"type": "string"},
                            "params": {"type": "object"},
                        },
                        "required": ["id", "type", "title", "agent", "instruction"],
                    },
                },
            },
            "required": ["kind", "description", "tasks"],
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        logger.info(
            "delegate_tasks input account=%s args=%s",
            account_name,
            args,
        )

        goal: str = (args.get("goal") or "").strip()
        files: Optional[List[str]] = args.get("files") or None
        instruction: str = (args.get("instruction") or "").strip()
        worker_agent: str = (args.get("worker_agent") or "colin").strip() or "colin"
        worker_agent = worker_agent.lower()

        if not goal:
            result = {"ok": False, "tool": self.name(), "error": "Missing 'goal' for delegate_tasks tool."}
            logger.info("delegate_tasks output account=%s ok=%s result=%s", account_name, False, result)
            return result

        if not instruction:
            instruction = goal

        description = goal
        tasks: List[Dict[str, Any]] = []

        if files:
            for idx, path in enumerate(files, start=1):
                title = f"Apply goal to {path}"
                task_id = f"task-{idx}"
                tasks.append(
                    {
                        "id": task_id,
                        "type": "task",
                        "title": title,
                        "agent": worker_agent,
                        "instruction": instruction,
                        "file": path,
                        "params": {"file": path},
                    }
                )
        else:
            tasks.append(
                {
                    "id": "task-1",
                    "type": "task",
                    "title": "Execute goal",
                    "agent": worker_agent,
                    "instruction": instruction,
                    "params": {},
                }
            )

        result = {
            "ok": True,
            "tool": self.name(),
            "kind": "tasklist",
            "description": description,
            "tasks": tasks,
        }
        logger.info("delegate_tasks output account=%s ok=%s tasks=%d", account_name, True, len(tasks))
        return result

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "") -> str:
        logger.info(
            "delegate_tasks raw_input account=%s call_id=%s arguments_raw=%s",
            account_name,
            call_id,
            arguments_raw,
        )
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        result_raw = json.dumps(result, ensure_ascii=False)
        logger.info(
            "delegate_tasks raw_output account=%s call_id=%s result_raw=%s",
            account_name,
            call_id,
            result_raw,
        )
        return result_raw
