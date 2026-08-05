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
from src.agent.agent_manager import AgentManager
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

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent

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


# ---------------------------------------------------------------------------
# ChatEvent kind mapping
# ---------------------------------------------------------------------------
# ChatEvent.kind is a Literal restricted to:
#   "user_message", "assistant_message", "assistant_tool_call",
#   "tool_result", "system_note", "summary"
#
# Automation-specific kinds are mapped to valid ones, with the original
# stored in metadata["automation_kind"].

_AUTOMATION_KIND_MAP = {
    "automation_command": "user_message",
    "task_completed": "system_note",
    "task_failed": "system_note",
    "automation_summary": "summary",
}


def _map_chat2_kind(automation_kind: str) -> str:
    """Map an automation-specific kind to a valid ChatEvent kind."""
    return _AUTOMATION_KIND_MAP.get(automation_kind, "system_note")


# ---------------------------------------------------------------------------


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
        chat2_store: Optional[Chat2Store] = None,
        llm_adapter: Optional[LLMAdapter] = None,
        agent_manager: Optional[AgentManager] = None,
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.prompt_builder = prompt_builder
        self.chat2_store = chat2_store
        self.llm_adapter = llm_adapter
        self.agent_manager = agent_manager

    # ------------------------------------------------------------------
    # Chat2 event helpers
    # ------------------------------------------------------------------

    def _ensure_chat2_session(self, conversation_id: str, account_name: str, agent_name: str) -> None:
        """Create a chat2 session if one doesn't exist for this conversation_id.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        if self.chat2_store.session_exists(conversation_id):
            return
        try:
            self.chat2_store.create_session(
                user_id=account_name,
                account_name=account_name,
                agent_name=agent_name,
                session_id=conversation_id,
            )
            logger.info(
                "chat2: created session %s for account=%s agent=%s",
                conversation_id,
                account_name,
                agent_name,
            )
        except Exception:
            logger.exception(
                "chat2: failed to create session %s for account=%s",
                conversation_id,
                account_name,
            )

    def _write_chat2_event(
        self,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        role: str,
        kind: str,
        payload: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write a single event to chat2 storage.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        try:
            self._ensure_chat2_session(conversation_id, account_name, agent_name)

            # Map automation-specific kind to a valid ChatEvent kind.
            mapped_kind = _map_chat2_kind(kind)
            meta = dict(metadata or {})
            # Preserve the original kind so consumers can distinguish automation events.
            meta["automation_kind"] = kind

            event = ChatEvent(
                role=role,
                actor=agent_name if role == "assistant" else account_name,
                kind=mapped_kind,
                payload=payload,
                metadata=meta,
            )
            self.chat2_store.add_event(conversation_id, event)
            logger.info(
                "chat2: wrote %s event for session=%s kind=%s (mapped from %s)",
                role,
                conversation_id,
                mapped_kind,
                kind,
            )
        except Exception:
            logger.exception(
                "chat2: failed to write event for session=%s",
                conversation_id,
            )

    # ------------------------------------------------------------------
    # Agent resolution
    # ------------------------------------------------------------------

    def _resolve_task_agent(
        self,
        task: Task,
        primary_agent: Agent,
        agent_name: str,
    ) -> Agent:
        """Resolve the agent to use for executing a task.

        If the task has an agent field set and it differs from the calling agent,
        look up the worker agent via AgentManager. Otherwise fall back to primary_agent.

        Returns the resolved Agent to use for this task.
        """
        task_agent_name = (task.agent or "").strip().lower()
        if not task_agent_name or task_agent_name == agent_name:
            logger.info(
                "AutomationProcessor: task '%s' agent=%s (same as caller=%s), using primary agent",
                task.name,
                task_agent_name or "(none)",
                agent_name,
            )
            return primary_agent

        # Task specifies a different agent — resolve it.
        logger.info(
            "AutomationProcessor: task '%s' requested agent=%s, caller=%s — resolving worker agent",
            task.name,
            task_agent_name,
            agent_name,
        )

        if self.agent_manager is not None:
            worker = self.agent_manager.get_agent(task_agent_name)
            if worker is not None:
                logger.info(
                    "AutomationProcessor: resolved worker agent '%s' for task '%s'",
                    task_agent_name,
                    task.name,
                )
                return worker
            else:
                logger.warning(
                    "AutomationProcessor: agent '%s' not found in AgentManager for task '%s', falling back to %s",
                    task_agent_name,
                    task.name,
                    agent_name,
                )

        # Fallback: if AgentManager is unavailable or agent not found, use primary_agent
        return primary_agent

    # ------------------------------------------------------------------
    # Core execution logic
    # ------------------------------------------------------------------

    def execute_tasklist(
        self,
        *,
        tasklist_id: str,
        mode: str,
        account_name: str,
        agent_name: str,
        conversation_id: str,
        context_name: str,
        primary_agent: Agent,
        account: Dict[str, Any],
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
        worker_agent: Optional[str] = None,
    ) -> str:
        """Execute a persisted tasklist by ID.

        This is the core execution loop, extracted from process_message() so it
        can be called directly (e.g. from a tool handler) without going through
        JSON command parsing.

        If worker_agent is provided, the named agent is resolved via AgentManager
        and used for ALL tasks (per-task _resolve_task_agent is skipped). When not
        provided, existing per-task resolution behavior is unchanged.

        Returns a human-readable result string.
        Raises ValueError if the tasklist is not found in storage.
        """
        logger.info(
            "execute_tasklist start agent=%s account=%s conversation_id=%s tasklist_id=%s mode=%s worker_agent=%s",
            agent_name,
            account_name,
            conversation_id,
            tasklist_id,
            mode,
            worker_agent,
        )

        # Resolve worker agent override (top-level, applies to ALL tasks).
        resolved_worker: Optional[Agent] = None
        resolved_worker_name: Optional[str] = None
        if worker_agent:
            worker_name = worker_agent.strip().lower()
            if self.agent_manager is not None:
                resolved_worker = self.agent_manager.get_agent(worker_name)
                if resolved_worker is not None:
                    resolved_worker_name = (
                        getattr(resolved_worker, "name", "") or ""
                    ).lower().strip()
                    logger.info(
                        "execute_tasklist: using worker agent '%s' for all tasks",
                        resolved_worker_name,
                    )
                else:
                    logger.warning(
                        "execute_tasklist: worker agent '%s' not found in AgentManager, "
                        "falling back to per-task resolution",
                        worker_name,
                    )
            else:
                logger.warning(
                    "execute_tasklist: agent_manager not available, "
                    "cannot resolve worker agent '%s'",
                    worker_name,
                )

        # Resolve tasklist: tasklist_id may be either a storage key (friendly name)
        # or a UUID (the tasklist's id field). Try direct key lookup first, then
        # fall back to searching all tasklists by their id field.
        raw_tasklist: Optional[TaskList] = None
        resolved_key: str = tasklist_id

        try:
            raw_tasklist = self.storage.get_tasklist(account_name, tasklist_id)
        except Exception as e:
            logger.exception("Failed loading tasklist from storage")
            raise ValueError(
                f"Tasklist '{tasklist_id}' could not be loaded from storage: {e}"
            ) from e

        if raw_tasklist is None:
            # Search all tasklists by matching the id field.
            try:
                all_keys = self.storage.list_tasklists(account_name)
            except Exception:
                all_keys = []
            for key in all_keys:
                try:
                    candidate = self.storage.get_tasklist(account_name, key)
                except Exception:
                    continue
                if candidate is not None and getattr(candidate, "id", None) == tasklist_id:
                    raw_tasklist = candidate
                    resolved_key = key
                    logger.info(
                        "execute_tasklist: resolved tasklist_id=%s to storage key=%s",
                        tasklist_id,
                        resolved_key,
                    )
                    break

        if raw_tasklist is None:
            raise ValueError(
                f"Tasklist '{tasklist_id}' not found in storage. "
                "Use tasklists_manage to list available tasklists, or delegate_tasks to create one."
            )

        if not isinstance(raw_tasklist, TaskList):
            raise ValueError(
                f"Storage returned an unexpected type for tasklist '{tasklist_id}'. "
                f"Expected TaskList, got {type(raw_tasklist).__name__}."
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

        # Determine the per-task iteration cap.
        # Use the resolved worker agent's config when available, otherwise primary_agent.
        cap_agent = resolved_worker if resolved_worker is not None else primary_agent
        worker_task_iterations = int(getattr(cap_agent, "task_max_iterations", 10) or 10)
        if worker_task_iterations <= 0:
            worker_task_iterations = 10

        while True:
            idx, task = _find_next_pending_task(tasklist)
            if task is None or idx is None:
                # Nothing to do.
                overall_state = TASK_LIST_STATE_COMPLETED
                break

            last_task_name = task.name or f"task#{idx}"

            # Resolve the agent for this specific task.
            # When a top-level worker_agent is set, use it for all tasks.
            # Otherwise fall back to per-task resolution via _resolve_task_agent.
            if resolved_worker is not None:
                task_agent = resolved_worker
                task_agent_name = resolved_worker_name or agent_name
            else:
                task_agent = self._resolve_task_agent(task, primary_agent, agent_name)
                task_agent_name = (getattr(task_agent, "name", "") or "").lower().strip()

            logger.info(
                "AutomationProcessor executing task id=%s name=%s task_agent=%s (caller=%s)",
                task.id,
                last_task_name,
                task_agent_name,
                agent_name,
            )

            try:
                _set_task_state(task, TASK_STATE_RUNNING)
            except Exception:
                logger.exception("Failed setting task running")

            # Persist checkpoint: task is now RUNNING.
            try:
                self.storage.save_tasklist(account_name, resolved_key, tasklist.to_dict())
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
                    self.storage.save_tasklist(account_name, resolved_key, tasklist.to_dict())
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
                    # Build the message for the task execution.
                    # Order:
                    # 1) tasklist.general_instructions
                    # 2) task.instructions
                    # 3) task.meta fields (format: name = value)
                    message_parts = []

                    general_instructions = (getattr(tasklist, "general_instructions", "") or "").strip()
                    if general_instructions:
                        message_parts.append(general_instructions)

                    task_instructions = (task.instructions or "").strip()
                    if task_instructions:
                        message_parts.append(task_instructions)

                    meta = task.meta or {}
                    # Extract attachment IDs from meta before building message text.
                    file_ids = None
                    image_ids = None
                    if isinstance(meta, dict):
                        # Support both 'files' (list) and 'file' (singular) for file IDs.
                        raw_files = meta.pop("files", None)
                        raw_file = meta.pop("file", None)
                        if isinstance(raw_files, list):
                            file_ids = [str(f) for f in raw_files]
                        elif raw_file is not None:
                            file_ids = [str(raw_file)]

                        raw_images = meta.pop("image_ids", None)
                        if isinstance(raw_images, list):
                            image_ids = [str(i) for i in raw_images]

                        for k, v in meta.items():
                            key = str(k).strip()
                            if not key:
                                continue
                            message_parts.append(f"{key} = {v}")

                    task_message = "\n".join(message_parts).strip()
                    if not task_message:
                        warning_messages.append(
                            f"Task '{last_task_name}' has no instructions; marking completed with warning."
                        )
                        task_result = {
                            "timestamp": _now_utc().isoformat(),
                            "warning": "Task has no instructions. Provide task.instructions to execute.",
                        }
                    else:
                        # --- Cap sub-call iterations per design doc step 2 ---
                        # Save and override the worker agent's max_function_call_iterations
                        # with task_max_iterations so each sub-task gets a small, clean budget.
                        original_max = task_agent.max_function_call_iterations
                        task_agent.max_function_call_iterations = worker_task_iterations
                        logger.info(
                            "AutomationProcessor: capping iterations for task=%s agent=%s from %d to %d",
                            last_task_name,
                            task_agent_name,
                            original_max,
                            worker_task_iterations,
                        )
                        try:
                            response = function_processor.process_message(
                                primary_agent=task_agent,
                                account=account,
                                message=task_message,
                                conversation_id=conversation_id,
                                context_name=context_name,
                                secondary_agent=secondary_agent,
                                processor_factory=processor_factory,
                                image_ids=image_ids,
                                file_ids=file_ids,
                            )
                        finally:
                            # Restore the original value so subsequent tasks and
                            # the calling code are not affected.
                            task_agent.max_function_call_iterations = original_max

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

            # Write task result event to chat2
            task_outcome = "completed" if task_error is None else "failed"
            self._write_chat2_event(
                conversation_id=conversation_id,
                account_name=account_name,
                agent_name=task_agent_name,
                role="assistant",
                kind=f"task_{task_outcome}",
                payload=json.dumps({
                    "task_id": task.id,
                    "task_name": last_task_name,
                    "outcome": task_outcome,
                    "error": task_error,
                }),
                metadata={"tasklist_id": tasklist_id, "mode": mode},
            )

            # Persist after each task (COMPLETED or FAILED checkpoint).
            try:
                self.storage.save_tasklist(account_name, resolved_key, tasklist.to_dict())
            except Exception as e:
                logger.exception("Failed persisting tasklist after task execution")
                overall_state = TASK_LIST_STATE_FAILED

                # Ensure tasklist end-state is marked FAILED and persisted before returning
                try:
                    tasklist.state = TASK_LIST_STATE_FAILED
                except Exception:
                    logger.exception("Failed setting tasklist state to FAILED after persist error")
                try:
                    self.storage.save_tasklist(account_name, resolved_key, tasklist.to_dict())
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

            self.storage.save_tasklist(account_name, resolved_key, tasklist.to_dict())
        except Exception:
            logger.exception("Failed final persist")

        # Write final summary event to chat2.
        # Use the resolved worker name when active, otherwise the caller's agent_name.
        summary_agent = resolved_worker_name if resolved_worker_name is not None else agent_name
        self._write_chat2_event(
            conversation_id=conversation_id,
            account_name=account_name,
            agent_name=summary_agent,
            role="assistant",
            kind="automation_summary",
            payload=json.dumps({
                "tasklist_id": tasklist_id,
                "mode": mode,
                "state": tasklist.state,
                "executed_count": executed_count,
                "last_task": last_task_name,
                "warnings": warning_messages,
            }),
            metadata={"tasklist_id": tasklist_id, "mode": mode},
        )

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

    # ------------------------------------------------------------------
    # Main processing (thin wrapper around execute_tasklist)
    # ------------------------------------------------------------------

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
                "Send JSON: {\"action\": \"run\", \"tasklist_id\": \"...\", \"mode\": \"multi-step\"}."
            )

        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"

        cmd, cmd_err = _parse_json_command(message)
        if cmd_err:
            return f"[AutomationProcessor] {cmd_err}"

        if not cmd:
            return (
                "[AutomationProcessor] This processor now expects a JSON command. "
                "Example: {\"action\": \"run\", \"tasklist_id\": \"my_tasklist_1\", \"mode\": \"multi-step\"}."
            )

        action = str(cmd.get("action") or "").lower().strip()
        if action not in {"run", "execute", "start"}:
            return (
                "[AutomationProcessor] Unknown action. "
                "Use {\"action\": \"run\", \"tasklist_id\": \"...\"}."
            )

        tasklist_id = str(cmd.get("tasklist_id") or "").strip()
        if not tasklist_id:
            return (
                "[AutomationProcessor] Missing required field 'tasklist_id'. "
                "Example: {\"action\": \"run\", \"tasklist_id\": \"my_tasklist_1\"}."
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

        # Write user command event to chat2
        self._write_chat2_event(
            conversation_id=conversation_id,
            account_name=account_name,
            agent_name=agent_name,
            role="user",
            kind="automation_command",
            payload=message,
            metadata={"tasklist_id": tasklist_id, "mode": mode},
        )

        # Delegate to the extracted execution method.
        # ValueError (e.g. tasklist not found) propagates up to the caller
        # so the tool handler can return ok=False with a proper error message.
        return self.execute_tasklist(
            tasklist_id=tasklist_id,
            mode=mode,
            account_name=account_name,
            agent_name=agent_name,
            conversation_id=conversation_id,
            context_name=context_name,
            primary_agent=primary_agent,
            account=account,
            secondary_agent=secondary_agent,
            processor_factory=processor_factory,
        )
