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
# Avoid importing Storage at module import time because storage.__init__ may import
# storage backends that depend on optional packages (pydantic). Use TYPE_CHECKING for typing only.
if TYPE_CHECKING:
    from src.storage.base import Storage

from src.tasklists import TaskList, Task, TaskModel, TaskListModel  # compatibility layer
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


def _coerce_tasklist(tasklist: Any) -> Tuple[Optional[Any], Optional[str]]:
    """Accept a stored tasklist in several shapes and return a usable object.

    Returns (tasklist_or_dict, error_message)
    """

    if tasklist is None:
        return None, "No tasklist present."

    # If a JSON string was stored, parse it.
    try:
        if isinstance(tasklist, str):
            parsed = json.loads(tasklist)
            return parsed, None
    except Exception as e:
        logger.exception("Failed to parse stored tasklist JSON")
        return None, f"Failed to parse tasklist JSON: {e}"

    # If it's already a dict or an object, return as-is; callers will handle dict vs object.
    if isinstance(tasklist, dict):
        return tasklist, None

    # For pydantic models or legacy classes, return as-is
    return tasklist, None


def _find_next_pending_task(tasklist: Any) -> Tuple[Optional[int], Optional[Any]]:
    """Return (index, task) for the next pending task.

    Supports both dict-shaped tasklists (with 'tasks' list) and object models
    with a 'tasks' attribute.
    """
    tasks = None
    if isinstance(tasklist, dict):
        tasks = tasklist.get("tasks") or []
    else:
        tasks = getattr(tasklist, "tasks", []) or []

    for idx, task in enumerate(tasks):
        # task may be dict or model
        state = None
        if isinstance(task, dict):
            state = task.get("state")
        else:
            state = getattr(task, "state", None)
        if state == TASK_STATE_PENDING:
            return idx, task
    return None, None


def _set_task_state(task: Any, state: str) -> None:
    """Set task.state safely for pydantic models or dicts."""

    if isinstance(task, dict):
        task["state"] = state
    else:
        try:
            setattr(task, "state", state)
        except Exception:
            # Some models may be immutable; fallback to setting in __dict__ if possible
            try:
                task.__dict__["state"] = state  # type: ignore
            except Exception:
                raise


def _serialize_tasklist(tasklist: Any) -> Dict[str, Any]:
    """Serialize TaskList-like object to a plain dict for persistence."""

    if tasklist is None:
        raise ValueError("Cannot serialize None tasklist")

    # If it's already a dict, return a shallow copy.
    if isinstance(tasklist, dict):
        return dict(tasklist)

    # Pydantic v2 models expose model_dump
    if hasattr(tasklist, "model_dump"):
        try:
            return tasklist.model_dump()
        except Exception:
            pass

    # Legacy TaskList may expose to_json
    if hasattr(tasklist, "to_json"):
        try:
            return json.loads(tasklist.to_json())
        except Exception:
            pass

    # Fallback: try to build a dict from attributes
    result: Dict[str, Any] = {}
    for attr in ("id", "state", "tasks", "meta", "current_task_id", "name"):
        if hasattr(tasklist, attr):
            val = getattr(tasklist, attr)
            # If tasks is list of models, convert each to dict if possible
            if attr == "tasks" and isinstance(val, list):
                serialized_tasks = []
                for t in val:
                    if isinstance(t, dict):
                        serialized_tasks.append(dict(t))
                    elif hasattr(t, "model_dump"):
                        try:
                            serialized_tasks.append(t.model_dump())
                        except Exception:
                            serialized_tasks.append(vars(t))
                    elif hasattr(t, "to_json"):
                        try:
                            serialized_tasks.append(json.loads(t.to_json()))
                        except Exception:
                            serialized_tasks.append(vars(t))
                    else:
                        try:
                            serialized_tasks.append(vars(t))
                        except Exception:
                            serialized_tasks.append(str(t))
                result["tasks"] = serialized_tasks
            else:
                result[attr] = val

    # Ensure id exists if present as attribute
    if not result and hasattr(tasklist, "__dict__"):
        try:
            result = dict(getattr(tasklist, "__dict__", {}))
        except Exception:
            pass

    return result


def _parse_json_command(message: str) -> Tuple[Optional[dict], Optional[str]]:
    """Parse inbound message as JSON.

    Returns (obj, error). If message is not valid JSON, obj is None.
    """

    raw = (message or "").strip()
    if not raw:
        return None, None

    try:
        obj = json.loads(raw)
    except Exception as e :
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
        storage: Any,
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
            # storage.get_tasklist may return dict, model or legacy object; _coerce_tasklist will
            # normalize for in-process use.
            raw_tasklist = self.storage.get_tasklist(account_name, tasklist_id)
        except Exception as e:
            logger.exception("Failed loading tasklist from storage")
            return f"[AutomationProcessor] mode={mode} tasklist_id={tasklist_id} not found: {e}"

        tasklist, err = _coerce_tasklist(raw_tasklist)
        if err:
            return f"[AutomationProcessor] Failed to load tasklist: {err}"

        # For compatibility, tasklist may be a dict or model/object. Update state via helpers.
        try:
            state_attr = tasklist.get("state") if isinstance(tasklist, dict) else getattr(tasklist, "state", None)
            if state_attr == TASK_LIST_STATE_CREATED:
                if isinstance(tasklist, dict):
                    tasklist["state"] = TASK_LIST_STATE_RUNNING
                else:
                    setattr(tasklist, "state", TASK_LIST_STATE_RUNNING)
        except Exception as e :
            logger.exception("Failed updating task list state", exc_info=e)

        overall_state = "running"
        executed_count = 0
        last_task_name = ""

        # Try to obtain a FunctionCallingProcessor from the factory if available.
        function_processor = None
        try:
            if processor_factory and hasattr(processor_factory, "get"):
                function_processor = processor_factory.get("function_calling_processor")
        except Exception:
            logger.exception("Failed to obtain function_calling_processor from processor_factory; falling back to no-op execution")
            function_processor = None

        while True:
            idx, task = _find_next_pending_task(tasklist)
            if task is None or idx is None:
                # Nothing to do.
                overall_state = "completed"
                break

            last_task_name = (
                getattr(task, "title", None)
                or getattr(task, "name", None)
                or (task.get("file_path") if isinstance(task, dict) else None)
                or f"task#{idx}"
            )

            task_id_log = getattr(task, "id", None) or (task.get("id") if isinstance(task, dict) else None)
            logger.info("AutomationProcessor executing task id=%s name=%s", task_id_log, last_task_name)

            try:
                _set_task_state(task, TASK_STATE_RUNNING)
            except Exception:
                logger.exception("Failed setting task running")

            # Persist checkpoint: task is now RUNNING.
            try:
                serialized_checkpoint = _serialize_tasklist(tasklist)
                self.storage.save_tasklist(account_name, tasklist_id, json.loads(json.dumps(serialized_checkpoint)))
            except Exception as e:
                logger.exception("Failed persisting tasklist (RUNNING checkpoint)")
                overall_state = "failed"
                try:
                    _set_task_state(task, TASK_STATE_FAILED)
                except Exception:
                    logger.exception("Failed setting task failed after persist error")
                # Ensure tasklist end-state is marked FAILED and persisted before returning
                try:
                    if isinstance(tasklist, dict):
                        tasklist["state"] = TASK_LIST_STATE_FAILED
                    else:
                        setattr(tasklist, "state", TASK_LIST_STATE_FAILED)
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED after persist error")
                try:
                    serialized = _serialize_tasklist(tasklist)
                    self.storage.save_tasklist(account_name, tasklist_id, json.loads(json.dumps(serialized)))
                except Exception:
                    logger.exception("Failed persisting tasklist after setting task FAILED")
                # Structured log
                logger.info(
                    "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                    tasklist_id,
                    task_id_log,
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
                    # Use the Agent object passed in (do not create new agents).
                    task_message = getattr(task, "title", None) or (task.get("title") if isinstance(task, dict) else "")
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
                if isinstance(task, dict):
                    task["result"] = task_result
                    if task_error is not None:
                        task["error"] = task_error
                else:
                    if hasattr(task, "result"):
                        setattr(task, "result", task_result)
                    if task_error is not None and hasattr(task, "error"):
                        setattr(task, "error", task_error)
            except Exception:
                logger.exception("Failed attaching result/error to task")

            # Set final state based on whether execution raised an error.
            try:
                if task_error is None:
                    _set_task_state(task, TASK_STATE_COMPLETED)
                else:
                    _set_task_state(task, TASK_STATE_FAILED)
                    overall_state = "failed"
            except Exception:
                logger.exception("Failed setting task completed/failed")
                overall_state = "failed"

            executed_count += 1

            # Persist after each task (COMPLETED or FAILED checkpoint).
            try:
                serialized = _serialize_tasklist(tasklist)
                self.storage.save_tasklist(account_name, tasklist_id, json.loads(json.dumps(serialized)))
            except Exception as e:
                logger.exception("Failed persisting tasklist after task execution")
                overall_state = "failed"
                # Ensure tasklist end-state is marked FAILED and persisted before returning
                try:
                    if isinstance(tasklist, dict):
                        tasklist["state"] = TASK_LIST_STATE_FAILED
                    else:
                        setattr(tasklist, "state", TASK_LIST_STATE_FAILED)
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED after persist error")
                try:
                    serialized = _serialize_tasklist(tasklist)
                    self.storage.save_tasklist(account_name, tasklist_id, json.loads(json.dumps(serialized)))
                except Exception:
                    logger.exception("Failed persisting tasklist after failure")
                # Structured log
                logger.info(
                    "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                    tasklist_id,
                    task_id_log,
                    mode,
                    overall_state,
                )
                return (
                    f"[AutomationProcessor] mode={mode} state=failed task='{last_task_name}' "
                    f"error='Failed to persist task state: {e}'"
                )

            if overall_state == "failed":
                break

            if mode != "multi-step":
                break

        # Final persist to ensure final list state saved.
        try:
            if overall_state == "completed":
                try:
                    if isinstance(tasklist, dict):
                        tasklist["state"] = TASK_LIST_STATE_COMPLETED
                    else:
                        setattr(tasklist, "state", TASK_LIST_STATE_COMPLETED)
                except Exception:
                    logger.exception("Failed setting tasklist state to COMPLETED")
            elif overall_state == "failed":
                try:
                    if isinstance(tasklist, dict):
                        tasklist["state"] = TASK_LIST_STATE_FAILED
                    else:
                        setattr(tasklist, "state", TASK_LIST_STATE_FAILED)
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED")
            serialized = _serialize_tasklist(tasklist)
            self.storage.save_tasklist(account_name, tasklist_id, json.loads(json.dumps(serialized)))
        except Exception:
            logger.exception("Failed final persist")

        # Structured final log for observability
        try:
            task_id_log = getattr(task, "id", None) or (task.get("id") if isinstance(task, dict) else None)
            logger.info(
                "AutomationProcessor end tasklist_id=%s task_id=%s mode=%s outcome=%s",
                tasklist_id,
                task_id_log,
                mode,
                overall_state,
            )
        except Exception:
            logger.exception("Failed logging final automation outcome")

        current_task_part = f"task='{last_task_name}'" if last_task_name else "task='(none)'"
        return f"[AutomationProcessor] mode={mode} state={overall_state} {current_task_part} executed={executed_count}"
