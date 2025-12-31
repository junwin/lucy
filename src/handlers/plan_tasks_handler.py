# src/handlers/plan_tasks_handler.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from .handler_v2 import HandlerV2


class PlanTasksHandler(HandlerV2):
    """Generate a simple task list from a goal and optional file list.

    This is a *planning* tool only. It does not execute the tasks; it just
    returns a JSON structure that can later be passed to a tasklist executor
    (e.g. inside FunctionCallingProcessor).
    """

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return "plan_tasks"

    # --- Tool definition -------------------------------------------------

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        """OpenAI tool definition for the plan_tasks tool.

        The model is expected to provide a high-level goal description and may
        optionally provide a list of files to focus on. The handler will
        normalize this into a simple sequential task list with one task per
        file (if files are provided) or a single task otherwise.
        """

        return {
            "type": "function",
            "function": {
                "name": cls.name(),
                "description": (
                    "Create a simple sequential task list for a coding or "
                    "refactoring task, given a goal and an optional list of files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal": {
                            "type": "string",
                            "description": (
                                "High-level description of the work to perform. "
                                "This should be written as instructions for a worker agent."
                            ),
                        },
                        "files": {
                            "type": "array",
                            "description": (
                                "Optional list of file paths to focus on. If provided, "
                                "the task list will contain one task per file."
                            ),
                            "items": {"type": "string"},
                        },
                        "instruction": {
                            "type": "string",
                            "description": (
                                "Optional detailed instruction template for each task. "
                                "If omitted, the goal will be used as the instruction."
                            ),
                        },
                        "worker_agent": {
                            "type": "string",
                            "description": (
                                "Optional name of the worker agent that should execute "
                                "the tasks (for documentation purposes)."
                            ),
                        },
                    },
                    "required": ["goal"],
                },
            },
        }

    # --- Result schema ---------------------------------------------------

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        """JSON schema for the task list result.

        This is intentionally minimal and matches the expectations of
        FunctionCallingProcessor._execute_simple_tasklist.
        """

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
                        "required": [
                            "id",
                            "type",
                            "title",
                            "agent",
                            "instruction",
                        ],
                    },
                },
            },
            "required": ["kind", "description", "tasks"],
        }

    # --- Execution -------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        goal: str = (args.get("goal") or "").strip()
        files: Optional[List[str]] = args.get("files") or None
        instruction: str = (args.get("instruction") or "").strip()
        worker_agent: str = (args.get("worker_agent") or "colin").strip() or "colin"

        if not goal:
            return {
                "ok": False,
                "error": "Missing 'goal' for plan_tasks tool.",
            }

        if not instruction:
            instruction = goal

        description = goal
        tasks: List[Dict[str, Any]] = []

        if files:
            # One task per file, assigned to the worker agent.
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
            # Single generic task, assigned to the worker agent.
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

        return {
            "ok": True,
            "tool": self.name(),
            "kind": "tasklist",
            "description": description,
            "tasks": tasks,
        }
