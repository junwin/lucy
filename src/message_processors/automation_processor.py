from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

# injector is optional in test environments; provide a noop inject decorator fallback.
try:
    from injector import inject  # type: ignore
except Exception:  # pragma: no cover - fallback for test environments
    def inject(func=None, *args, **kwargs):
        if func is None:
            def _decorate(f):
                return f

            return _decorate
        return func

from src.agent import Agent
from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface

if TYPE_CHECKING:
    from src.storage.base import Storage
    from src.tasklists.task_list import TaskList
    from src.tasklists.task import Task
    from src.tasklists.task_list import TaskListStorage
else:
    # Avoid importing storage/tasklist implementation modules at runtime during tests
    Storage = Any  # type: ignore
    TaskList = Any  # type: ignore
    Task = Any  # type: ignore
    TaskListStorage = Any  # type: ignore

from src.tasklists.task_states import (
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_LIST_STATE_COMPLETED,
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


def _coerce_tasklist(tasklist: Any) -> Tuple[Optional[TaskList], Optional[str]]:
    """Convert persisted tasklist into a TaskList.

    Returns (tasklist, error_message)
    """

    if tasklist is None:
        return None, "No tasklist present."

    try:
        if isinstance(tasklist, str):
            return TaskList.from_json(tasklist), None
        if isinstance(tasklist, dict):
            # Preserve any top-level runs metadata by attaching it onto the
            # constructed TaskList object. TaskList.from_json / from_dict do not
            # currently preserve arbitrary storage metadata, so we explicitly
            # carry runs across here so automation runs are persisted.
            tl = TaskList.from_json(json.dumps(tasklist))
            # Preserve any top-level runs metadata by attaching it onto the
            # constructed TaskList object. The persisted dict may contain a
            # 'runs' key which we want available on the TaskList instance so
            # automation runs are visible and persisted.
            runs = tasklist.get("runs")
            if isinstance(runs, dict):
                try:
                    setattr(tl, "runs", runs)
                except Exception:
                    logger.exception("Failed attaching runs metadata onto TaskList")
            return tl, None

        return None, f"Unsupported tasklist type: {type(tasklist)!r}"
    except Exception as e:
        logger.exception("Failed to parse tasklist")
        return None, f"Failed to parse tasklist: {e}"


def _find_next_pending_task(tasklist: TaskList) -> Tuple[Optional[int], Optional[Any]]:
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


def _serialize_tasklist(tasklist: TaskList) -> Dict[str, Any]:
    """Serialize TaskList to a plain dict for persistence."""

    # TaskList is not pydantic; it has to_json.
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

        # Accept JSON payloads to allow creating/resuming runs via message body.
        # If message is JSON and contains {"action": "run", ...} then parse fields.
        mode = _parse_execution_mode_from_text(message)
        run_id = None
        run_name = None
        try:
            raw = (message or "").strip()
            if raw:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    action = str(obj.get("action", "")).lower().strip()
                    if action in {"run", "execute", "start"}:
                        mode = str(obj.get("mode", mode)).lower() or mode
                        run_id = obj.get("run_id") or obj.get("id")
                        run_name = obj.get("name")
        except Exception:
            # Not JSON or parse failed; fall back to free-text parsing above.
            pass

        if not _is_run_command(message):
            return (
                "[AutomationProcessor] Unknown or invalid command. "
                "Try: 'run tasks' (optionally 'single step' or 'multi-step')."
            )

        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"

        logger.info(
            "AutomationProcessor start agent=%s account=%s conversation_id=%s context=%s mode=%s run_id=%s",
            agent_name,
            account_name,
            conversation_id,
            context_name,
            mode,
            run_id,
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

        tasklist = None
        try:
            data = getattr(ctx, "data", None)
            if isinstance(data, dict):
                tasklist = data.get("tasklist")
            else:
                tasklist = getattr(data, "tasklist", None)
        except Exception:
            logger.exception("Failed reading tasklist from context")

        if not tasklist:
            logger.info("Context present but missing tasklist context=%s", context_name)
            return (
                f"[AutomationProcessor] mode={mode} no task list found in context '{context_name}'. "
                "Expected context.data.tasklist. Create a task list first."
            )

        tasklist, err = _coerce_tasklist(tasklist)
        if err or tasklist is None:
            return f"[AutomationProcessor] mode={mode} {err}"

        # If a run_id is provided, attempt to resume by finding matching run metadata
        # stored inside tasklist.runs (a dict keyed by run_id). Otherwise create a new run entry.
        runs = getattr(tasklist, "runs", None) or {}
        run_obj = None
        if run_id:
            run_obj = runs.get(run_id) if isinstance(runs, dict) else None
            if run_obj is None:
                logger.info("Run id provided but not found in tasklist runs: %s", run_id)

        if run_obj is None:
            # create a run entry
            run_id = run_id or f"run-{_now_utc().isoformat()}"
            run_obj = {
                "id": run_id,
                "name": run_name or getattr(tasklist, "title", None) or "(run)",
                "state": "created",
                "created_at": _now_utc().isoformat(),
                "updated_at": _now_utc().isoformat(),
                "executed_count": 0,
            }
            # attach to tasklist.runs (ensure it's a dict)
            try:
                if isinstance(runs, dict):
                    runs[run_id] = run_obj
                else:
                    setattr(tasklist, "runs", {run_id: run_obj})
            except Exception:
                logger.exception("Failed attaching run metadata to tasklist")

        # Mark list state running if it was created.
        try:
            if getattr(tasklist, "state", None) == TASK_LIST_STATE_CREATED:
                tasklist.state = TASK_LIST_STATE_RUNNING
            run_obj["state"] = "running"
            run_obj["updated_at"] = _now_utc().isoformat()
        except Exception:
            logger.exception("Failed updating task list/run state")

        overall_state = "running"
        executed_count = run_obj.get("executed_count", 0) if isinstance(run_obj, dict) else 0
        last_task_name = ""

        while True:
            idx, task = _find_next_pending_task(tasklist)
            if task is None or idx is None:
                try:
                    tasklist.state = TASK_LIST_STATE_COMPLETED
                except Exception:
                    logger.exception("Failed setting task list completed")
                overall_state = "completed"
                run_obj["state"] = "completed"
                run_obj["updated_at"] = _now_utc().isoformat()
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
            if isinstance(run_obj, dict):
                run_obj["executed_count"] = executed_count
                run_obj["updated_at"] = _now_utc().isoformat()

            # persist after each state change
            try:
                serialized = _serialize_tasklist(tasklist)

                data = getattr(ctx, "data", None)
                if isinstance(data, dict):
                    data["tasklist"] = serialized
                else:
                    setattr(data, "tasklist", serialized)

                self.storage.save_context(ctx)
            except Exception as e:
                logger.exception("Failed persisting context/tasklist")
                overall_state = "failed"
                run_obj["state"] = "failed"
                run_obj["updated_at"] = _now_utc().isoformat()
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
                data["tasklist"] = serialized
            else:
                setattr(data, "tasklist", serialized)
            self.storage.save_context(ctx)
        except Exception:
            logger.exception("Failed final persist")

        current_task_part = f"task='{last_task_name}'" if last_task_name else "task='(none)'"
        return f"[AutomationProcessor] mode={mode} state={overall_state} {current_task_part} executed={executed_count}"
