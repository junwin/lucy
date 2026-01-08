from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from injector import inject

from src.agent import Agent
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.storage.base import Storage
from src.tasklists.file_tasklist import FileTaskList
from src.tasklists.tasklist_interface import (
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
)

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_preview(text: str, limit: int = 500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _is_run_command(message: str) -> bool:
    """Very small command parser.

    Intended behavior for now:
    - If message asks to run tasks, proceed.
    - Otherwise return a helpful error.

    Accepts either free text containing 'run' + 'task(s)' or JSON like:
      {"action": "run"}
    """

    raw = (message or "").strip()
    if not raw:
        return False

    # JSON command
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            action = str(obj.get("action", "")).lower().strip()
            if action in {"run", "execute", "start"}:
                return True
    except Exception:
        pass

    # Free text
    text = raw.lower()
    return ("run" in text or "execute" in text or "start" in text) and (
        "task" in text or "tasks" in text
    )


def _parse_execution_mode_from_text(message: str) -> str:
    """Parse execution mode from free-text.

    Supported: 'single-step' or 'multi-step'. Default: 'single-step'.

    Accepts variants like: "single step", "multi step", case-insensitive.
    """

    text = (message or "").lower().strip()
    if not text:
        return "single-step"

    normalized = text.replace("-", " ")
    if "multi" in normalized and "step" in normalized:
        return "multi-step"
    if "single" in normalized and "step" in normalized:
        return "single-step"

    # Default if no explicit mode requested.
    return "single-step"


def _coerce_tasklist(tasklist_json: Any) -> Tuple[Optional[FileTaskList], Optional[str]]:
    """Convert persisted tasklist_json into a FileTaskList.

    Returns (tasklist, error_message)
    """

    if tasklist_json is None:
        return None, "No tasklist_json present."

    try:
        if isinstance(tasklist_json, str):
            return FileTaskList.from_json(tasklist_json), None
        if isinstance(tasklist_json, dict):
            return FileTaskList.from_json(json.dumps(tasklist_json)), None

        return None, f"Unsupported tasklist_json type: {type(tasklist_json)!r}"
    except Exception as e:
        logger.exception("Failed to parse tasklist_json")
        return None, f"Failed to parse tasklist_json: {e}"


def _find_next_pending_task(tasklist: FileTaskList) -> Tuple[Optional[int], Optional[Any]]:
    """Return (index, task) for the next pending task."""

    tasks = getattr(tasklist, "tasks", None) or []
    for idx, task in enumerate(tasks):
        state = getattr(task, "state", None)
        if state == TASK_STATE_PENDING:
            return idx, task
    return None, None


def _set_task_state(task: Any, state: str) -> None:
    """Set task.state safely for pydantic models or dicts."""

    if isinstance(task, dict):
        task["state"] = state
    else:
        setattr(task, "state", state)


def _serialize_tasklist(tasklist: FileTaskList) -> Dict[str, Any]:
    """Serialize FileTaskList to a plain dict for persistence."""

    # FileTaskList is not pydantic; it has to_json.
    return json.loads(tasklist.to_json())


class AutomationProcessor(MessageProcessorInterface):
    """Automation processor for running persisted task lists.

    For Part 1+2, this does not execute external tools; it only updates task
    state and stores placeholder results.
    """

    @inject
    def __init__(
        self,
        config: ConfigManager,
        registry: "HandlerRegistry",
        storage: Storage,
        prompt_builder: PromptBuilderInterface,
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.prompt_builder = prompt_builder

    def process_message(
        self,
        *,
        primary_agent: Agent,
        account: Dict[str, Any],
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        agent_name = (getattr(primary_agent, "name", "") or "").lower().strip()
        if agent_name != "doris":
            logger.debug("AutomationProcessor ignoring agent=%s", agent_name)
            return f"[AutomationProcessor] Not responsible for agent '{agent_name}'."

        if not context_name:
            logger.warning("AutomationProcessor missing context_name")
            return "[AutomationProcessor] Missing context_name. Provide a context_name to run automation."

        if not _is_run_command(message):
            return (
                "[AutomationProcessor] Unknown or invalid command. "
                "Try: 'run tasks' (optionally 'single step' or 'multi-step')."
            )

        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"
        mode = _parse_execution_mode_from_text(message)

        logger.info(
            "AutomationProcessor start agent=%s account=%s conversation_id=%s context=%s mode=%s",
            agent_name,
            account_name,
            conversation_id,
            context_name,
            mode,
        )
        logger.debug("Incoming message preview: %s", _safe_preview(message, 800))

        # Load existing context (do not create).
        try:
            ctx = self.storage.get_context(account_name, context_name)
        except Exception as e:
            logger.exception("Failed loading context")
            return f"[AutomationProcessor] mode={mode} context '{context_name}' not found: {e}"

        if ctx is None:
            return f"[AutomationProcessor] mode={mode} context '{context_name}' not found."

        tasklist_json = None
        try:
            data = getattr(ctx, "data", None)
            if isinstance(data, dict):
                tasklist_json = data.get("tasklist_json")
            else:
                tasklist_json = getattr(data, "tasklist_json", None)
        except Exception:
            logger.exception("Failed reading tasklist_json from context")

        if not tasklist_json:
            logger.info("Context present but missing tasklist_json context=%s", context_name)
            return (
                f"[AutomationProcessor] mode={mode} no task list found in context '{context_name}'. "
                "Expected context.data.tasklist_json. Create a task list first."
            )

        tasklist, err = _coerce_tasklist(tasklist_json)
        if err or tasklist is None:
            return f"[AutomationProcessor] mode={mode} {err}"

        # Mark list state running if it was created.
        try:
            if getattr(tasklist, "state", None) == TASK_LIST_STATE_CREATED:
                tasklist.state = TASK_LIST_STATE_RUNNING
        except Exception:
            logger.exception("Failed updating task list state")

        overall_state = "running"
        executed_count = 0
        last_task_name = ""

        while True:
            idx, task = _find_next_pending_task(tasklist)
            if task is None or idx is None:
                try:
                    tasklist.state = TASK_LIST_STATE_COMPLETED
                except Exception:
                    logger.exception("Failed setting task list completed")
                overall_state = "completed"
                break

            last_task_name = (
                getattr(task, "title", None)
                or getattr(task, "name", None)
                or getattr(task, "file_path", None)
                or f"task#{idx}"
            )

            try:
                _set_task_state(task, TASK_STATE_RUNNING)
            except Exception:
                logger.exception("Failed setting task running")

            placeholder_result = {
                "timestamp": _now_utc().isoformat(),
                "note": "Placeholder result. External tool execution disabled for Part 1+2.",
                "intended_action": {
                    "task": last_task_name,
                    "mode": mode,
                },
            }

            logger.info(
                "AutomationProcessor intended action (no-op): task=%s index=%s mode=%s",
                last_task_name,
                idx,
                mode,
            )

            try:
                if isinstance(task, dict):
                    task["result"] = placeholder_result
                else:
                    if hasattr(task, "result"):
                        setattr(task, "result", placeholder_result)
            except Exception:
                logger.exception("Failed attaching placeholder result")

            try:
                _set_task_state(task, TASK_STATE_COMPLETED)
            except Exception:
                logger.exception("Failed setting task completed")
                overall_state = "failed"

            executed_count += 1

            try:
                serialized = _serialize_tasklist(tasklist)

                data = getattr(ctx, "data", None)
                if isinstance(data, dict):
                    data["tasklist_json"] = serialized
                else:
                    setattr(data, "tasklist_json", serialized)

                self.storage.save_context(ctx)
            except Exception as e:
                logger.exception("Failed persisting context/tasklist")
                overall_state = "failed"
                return (
                    f"[AutomationProcessor] mode={mode} state=failed task='{last_task_name}' "
                    f"error='Failed to persist task state: {e}'"
                )

            if overall_state == "failed":
                break

            if mode != "multi-step":
                break

        try:
            serialized = _serialize_tasklist(tasklist)
            data = getattr(ctx, "data", None)
            if isinstance(data, dict):
                data["tasklist_json"] = serialized
            else:
                setattr(data, "tasklist_json", serialized)
            self.storage.save_context(ctx)
        except Exception:
            logger.exception("Failed final persist")

        current_task_part = f"task='{last_task_name}'" if last_task_name else "task='(none)'"
        return f"[AutomationProcessor] mode={mode} state={overall_state} {current_task_part} executed={executed_count}"
