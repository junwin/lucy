from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

try:
    from injector import inject
except Exception:
    # Minimal shim for environments without the "injector" package (tests run in minimal environments).
    # The shim simply returns the function unchanged so the decorator has no effect.
    def inject(func):
        return func

from src.agent import Agent
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.storage.base import Storage
from src.storage.models import ChatMessage

# Avoid importing Storage at module import time because storage.__init__ may import
# storage backends that depend on optional packages (pydantic). Use TYPE_CHECKING for typing only.
if TYPE_CHECKING:
    from src.storage.base import Storage

from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_FAILED,
    TASK_LIST_STATE_RUNNING,
)

from src.llm.adapter_interface import LLMAdapter

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


def _find_next_pending_task(tasklist: TaskList) -> Tuple[Optional[int], Optional[Task]]:
    """Return (index, task) for the next pending task."""

    tasks = tasklist.tasks or []
    for idx, task in enumerate(tasks):
        if task.state == TASK_STATE_PENDING:
            return idx, task
    return None, None


def _set_task_state(task: Task, state: str) -> None:
    task.state = state


def _parse_json_command(message: str) -> Tuple[Optional[dict], Optional[str]]:
    """Parse inbound message as JSON.

    Returns (obj, error). If message is not valid JSON, obj is None.
    """

    raw = (message or "").strip()
    if not raw:
        return None, None

    try:
        obj = json.loads(raw)
    except Exception as e:
        return None, f"Invalid JSON: {e}"

    if not isinstance(obj, dict):
        return None, "JSON command must be an object."

    return obj, None


class AutomationProcessor(MessageProcessorInterface):
    """Automation processor for running persisted task lists.

    For Part 1+2, this does not execute external tools; it only updates task
    state and stores placeholder results.

    Option A (recommended): JSON command
      {"action": "run", "tasklist_id": "my_tasklist_1", "mode": "multi-step"}

    This processor does not use context for tasklist access.
    """

    @inject
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        storage: Storage,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: Optional[LLMAdapter] = None,
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter

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

        # Keep context_name requirement for compatibility with the processor interface,
        # but do not use it for tasklist access.
        if not context_name:
            logger.warning("AutomationProcessor missing context_name")
            return "[AutomationProcessor] Missing context_name."

        if not _is_run_command(message):
            return (
                "[AutomationProcessor] Unknown or invalid command. "
                "Send JSON: {\\\"action\\\": \\\"run\\\", \\\"tasklist_id\\\": \\\"...\\\", \\\"mode\\\": \\\"multi-step\\\"}."
            )

        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"

        cmd, cmd_err = _parse_json_command(message)
        if cmd_err:
            return f"[AutomationProcessor] {cmd_err}"

        if not cmd:
            return (
                "[AutomationProcessor] This processor now expects a JSON command. "
                "Example: {\\\"action\\\": \\\"run\\\", \\\"tasklist_id\\\": \\\"my_tasklist_1\\\", \\\"mode\\\": \\\"multi-step\\\"}."
            )

        action = str(cmd.get("action") or "").lower().strip()
        if action not in {"run", "execute", "start"}:
            return (
                "[AutomationProcessor] Unknown action. "
                "Use {\\\"action\\\": \\\"run\\\", \\\"tasklist_id\\\": \\\"...\\\"}."
            )

        tasklist_id = str(cmd.get("tasklist_id") or "").strip()
        if not tasklist_id:
            return (
                "[AutomationProcessor] Missing required field 'tasklist_id'. "
                "Example: {\\\"action\\\": \\\"run\\\", \\\"tasklist_id\\\": \\\"my_tasklist_1\\\"}."
            )

        mode = str(cmd.get("mode") or "").strip() or "single-step"
        if mode not in {"single-step", "multi-step"}:
            return "[AutomationProcessor] Invalid mode. Use 'single-step' or 'multi-step'."

        logger.info(
            "AutomationProcessor start agent=%s account=%s conversation_id=%s tasklist_id=%s mode=%s",
            agent_name,
            account_name,
            conversation_id,
            tasklist_id,
            mode,
        )
        logger.debug("Incoming message preview: %s", _safe_preview(message, 800))

        try:
            raw_tasklist = self.storage.get_tasklist(account_name, tasklist_id)
        except Exception as e:
            logger.exception("Failed loading tasklist from storage")
            return f"[AutomationProcessor] mode={mode} tasklist_id={tasklist_id} not found: {e}"

        if not isinstance(raw_tasklist, TaskList):
            return (
                "[AutomationProcessor] Storage returned an unexpected tasklist type. "
                "Expected TaskList."
            )

        tasklist: TaskList = raw_tasklist

        try:
            if tasklist.state == TASK_LIST_STATE_CREATED:
                tasklist.state = TASK_LIST_STATE_RUNNING
        except Exception as e:
            logger.exception("Failed updating task list state", exc_info=e)

        overall_state = TASK_LIST_STATE_RUNNING
        executed_count = 0
        last_task_name = ""
        warning_messages: list[str] = []

        # Try to obtain a FunctionCallingProcessor from the factory if available.
        function_processor = None
        try:
            if processor_factory and hasattr(processor_factory, "get"):
                function_processor = processor_factory.get("function_calling_processor")
        except Exception:
            logger.exception(
                "Failed to obtain function_calling_processor from processor_factory; falling back to no-op execution"
            )
            function_processor = None

        while True:
            idx, task = _find_next_pending_task(tasklist)
            if task is None or idx is None:
                # Nothing to do.
                overall_state = TASK_LIST_STATE_COMPLETED
                break

            last_task_name = task.name or f"task#{idx}"

            logger.info(
                "AutomationProcessor executing task id=%s name=%s",
                task.id,
                last_task_name,
            )

            try:
                _set_task_state(task, TASK_STATE_RUNNING)
            except Exception:
                logger.exception("Failed setting task running")

            # Persist checkpoint: task is now RUNNING.
            try:
                self.storage.save_tasklist(account_name, tasklist_id, tasklist.to_dict())
            except Exception as e:
                logger.exception("Failed persisting tasklist (RUNNING checkpoint)")
                overall_state = TASK_LIST_STATE_FAILED
                try:
                    _set_task_state(task, TASK_STATE_FAILED)
                except Exception:
                    logger.exception("Failed setting task failed after persist error")

                # Ensure tasklist end-state is marked FAILED and persisted before returning
                try:
                    tasklist.state = TASK_LIST_STATE_FAILED
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED after persist error")
                try:
                    self.storage.save_tasklist(account_name, tasklist_id, tasklist.to_dict())
                except Exception:
                    logger.exception("Failed persisting tasklist after setting task FAILED")

                logger.info(
                    "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                    tasklist_id,
                    task.id,
                    mode,
                    overall_state,
                )
                return (
                    f"[AutomationProcessor] mode={mode} state=failed task='{last_task_name}' "
                    f"error='Failed to persist RUNNING checkpoint: {e}'"
                )

            # Execute the task using the FunctionCallingProcessor if available;
            # otherwise attach a placeholder result.
            task_result = None
            task_error = None
            try:
                if function_processor is not None:
                    task_message = (task.instructions or "").strip()
                    if not task_message:
                        warning_messages.append(
                            f"Task '{last_task_name}' has no instructions; marking completed with warning."
                        )
                        task_result = {
                            "timestamp": _now_utc().isoformat(),
                            "warning": "Task has no instructions. Provide task.instructions to execute.",
                        }
                    else:
                        response = function_processor.process_message(
                            primary_agent=primary_agent,
                            account=account,
                            message=task_message,
                            conversation_id=conversation_id,
                            context_name=context_name,
                            secondary_agent=secondary_agent,
                            processor_factory=processor_factory,
                        )
                        task_result = {"timestamp": _now_utc().isoformat(), "output": response}
                else:
                    task_result = {
                        "timestamp": _now_utc().isoformat(),
                        "note": "Placeholder result. External tool execution disabled for Part 1+2.",
                        "intended_action": {"task": last_task_name, "mode": mode},
                    }
            except Exception as e:
                logger.exception("Task execution failed for task=%s", last_task_name)
                task_error = str(e)

            try:
                task.result = task_result
                if task_error is not None:
                    task.error = task_error
            except Exception:
                logger.exception("Failed attaching result/error to task")

            # Set final state based on whether execution raised an error.
            try:
                if task_error is None:
                    _set_task_state(task, TASK_STATE_COMPLETED)
                else:
                    _set_task_state(task, TASK_STATE_FAILED)
                    overall_state = TASK_LIST_STATE_FAILED
            except Exception:
                logger.exception("Failed setting task completed/failed")
                overall_state = TASK_LIST_STATE_FAILED

            executed_count += 1

            # Persist after each task (COMPLETED or FAILED checkpoint).
            try:
                self.storage.save_tasklist(account_name, tasklist_id, tasklist.to_dict())
            except Exception as e:
                logger.exception("Failed persisting tasklist after task execution")
                overall_state = TASK_LIST_STATE_FAILED

                # Ensure tasklist end-state is marked FAILED and persisted before returning
                try:
                    tasklist.state = TASK_LIST_STATE_FAILED
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED after persist error")
                try:
                    self.storage.save_tasklist(account_name, tasklist_id, tasklist.to_dict())
                except Exception:
                    logger.exception("Failed persisting tasklist after failure")

                logger.info(
                    "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                    tasklist_id,
                    task.id,
                    mode,
                    overall_state,
                )
                return (
                    f"[AutomationProcessor] mode={mode} state=failed task='{last_task_name}' "
                    f"error='Failed to persist task state: {e}'"
                )

            if overall_state == TASK_LIST_STATE_FAILED:
                break

            if mode != "multi-step":
                break

        # Final persist to ensure final list state saved.
        try:
            if overall_state == TASK_LIST_STATE_COMPLETED:
                try:
                    tasklist.state = TASK_LIST_STATE_COMPLETED
                except Exception:
                    logger.exception("Failed setting tasklist state to COMPLETED")
            elif overall_state == TASK_LIST_STATE_FAILED:
                try:
                    tasklist.state = TASK_LIST_STATE_FAILED
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED")

            self.storage.save_tasklist(account_name, tasklist_id, tasklist.to_dict())
        except Exception:
            logger.exception("Failed final persist")

        # Structured final log for observability
        try:
            logger.info(
                "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                tasklist_id,
                task.id if task else None,
                mode,
                overall_state,
            )
        except Exception:
            logger.exception("Failed logging final automation outcome")

        current_task_part = f"task='{last_task_name}'" if last_task_name else "task='(none)'"
        warning_part = (
            f" warnings={json.dumps(warning_messages)}" if warning_messages else ""
        )
        return (
            f"[AutomationProcessor] mode={mode} state={tasklist.state} {current_task_part} "
            f"executed={executed_count}{warning_part}"
        )
