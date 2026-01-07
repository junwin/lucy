from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from injector import inject

from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.message_processors.types import AccountDict, AgentDict
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.storage.base import Storage
from src.storage.models import ChatMessage
from src.agent import Agent
from src.tasklists.file_tasklist import FileTaskList
from src.tasklists.tasklist_interface import (
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_LIST_STATE_COMPLETED,
    TASK_STATE_PENDING,
    TASK_STATE_COMPLETED,
)

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_preview(text: str, limit: int = 500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


class AutomationProcessor(MessageProcessorInterface):
    """Automation processor for running persisted task lists.

    Behaviour:
    - Only handles the supervisor agent "doris".
    - Supports command messages (JSON) like {"action": "run"}.
    - Loads the task list from Storage ContextState using `context_name`.
    - Enforces an "agreed" gate before running.
    - Persists progress after each task so runs are restartable.

    Context storage contract (ContextState.data):
      - tasklist_json: str (FileTaskList JSON)
      - task_list_id: str (optional convenience)
      - tasklist_status: draft|proposed|agreed|rejected|running|completed (optional)
      - agreed: bool (source of truth for approval)
      - agreed_at: str (ISO) (optional)
      - agreed_by: str (optional)
      - rejected_reason: str (optional)

    Note: We intentionally treat context.data['agreed'] as the source of truth
    (not task_list.extra['agreed']).
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
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        agent_name = (primary_agent.name or "").lower().strip()
        if agent_name != "doris":
            logger.debug("AutomationProcessor ignoring agent=%s", agent_name)
            return f"[AutomationProcessor] Not responsible for agent '{agent_name}'."

        store_this_call = bool(primary_agent.save_responses)
        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"

        logger.info(
            "AutomationProcessor start agent=%s account=%s conversation_id=%s context=%s",
            agent_name,
            account_name,
            conversation_id,
            context_name,
        )
        logger.debug("Incoming message preview: %s", _safe_preview(message, 800))

        if not context_name:
            logger.warning("Missing context_name")
            return "[AutomationProcessor] Missing context_name. Provide a context like 'junwin.lucy.XYZ'."

        worker_name = secondary_agent.name

        worker_name = worker_name.lower().strip()
        worker_processor = (
            processor_factory.get("function_calling_processor") if processor_factory else None
        )
        if worker_processor is None:
            logger.error("Missing worker processor (function_calling_processor)")
            return "[AutomationProcessor] Missing worker processor (function_calling_processor)."

        # Parse message as command JSON if possible.
        #
        # IMPORTANT:
        # - We only treat the inbound message as a tasklist override if it looks like a tasklist JSON.
        # - Random text should not be treated as JSON; we return a polite help message instead.
        cmd: Dict[str, Any] = {}
        raw_message = (message or "").strip()
        if raw_message:
            try:
                parsed = json.loads(raw_message)
                if isinstance(parsed, dict):
                    cmd = parsed
                    logger.debug("Parsed command JSON: %s", cmd)
                else:
                    # JSON but not a dict (e.g., list/string/number). Do not treat as tasklist.
                    logger.info(
                        "Message JSON parsed but not a dict; returning help. type=%s",
                        type(parsed).__name__,
                    )
                    return (
                        "[AutomationProcessor] I expected a JSON object command like "
                        "{\"action\":\"status\"} or {\"action\":\"run\"}. "
                        "If you want to run a tasklist, store it in context.data['tasklist_json'] first."
                    )
            except Exception:
                # Not JSON at all: treat as a normal chat message, not a tasklist override.
                logger.info("Message is not JSON; returning help")
                return (
                    "[AutomationProcessor] I expected a JSON command. Supported commands: "
                    "{\"action\":\"status\"}, {\"action\":\"run\"}, {\"action\":\"resume\"}, "
                    "{\"action\":\"reject\",\"reason\":...}. "
                    "To run automation, Lucy must first store a tasklist in context.data['tasklist_json']."
                )
        else:
            cmd = {"action": "status"}

        action = (cmd.get("action") or "status").lower().strip()
        logger.info("AutomationProcessor action=%s worker=%s", action, worker_name)

        # Load context
        context = self.storage.get_context(account_name, context_name)
        if context is None:
            logger.error("Context not found account=%s context=%s", account_name, context_name)
            return f"[AutomationProcessor] Context '{context_name}' not found for account '{account_name}'."

        # Load tasklist JSON either from command override or from context.
        # NOTE: cmd.get('tasklist_json') may be present but empty (""), which should not override
        # a valid context value.
        tasklist_json = cmd.get("tasklist_json")
        if isinstance(tasklist_json, str):
            tasklist_json = tasklist_json.strip()
        if not tasklist_json:
            tasklist_json = (context.data or {}).get("tasklist_json")
        tasklist_json = (tasklist_json or "").strip()

        if not tasklist_json:
            logger.warning(
                "No tasklist_json in context account=%s context=%s", account_name, context_name
            )
            return (
                f"[AutomationProcessor] No tasklist found in context '{context_name}'. "
                "Lucy should store context.data['tasklist_json'] first."
            )

        try:
            task_list = FileTaskList.from_json(tasklist_json)
        except Exception as e:
            logger.exception("Failed to parse tasklist_json from context")
            return f"[AutomationProcessor] Failed to parse tasklist_json from context: {e}"

        logger.info(
            "Loaded tasklist id=%s state=%s tasks=%s",
            task_list.task_list_id,
            task_list.state,
            len(task_list.tasks()),
        )
        logger.debug(
            "Context flags: agreed=%s tasklist_status=%s",
            (context.data or {}).get("agreed"),
            (context.data or {}).get("tasklist_status"),
        )

        # Helper: persist tasklist back into context after changes
        def persist(task_list_to_save: FileTaskList, *, status: Optional[str] = None) -> None:
            context.data = context.data or {}
            context.data["tasklist_json"] = task_list_to_save.to_json(indent=2)
            context.data["task_list_id"] = task_list_to_save.task_list_id
            if status is not None:
                context.data["tasklist_status"] = status
            context.updated_at = _now_utc()
            self.storage.save_context(context)
            logger.debug(
                "Persisted tasklist id=%s status=%s state=%s",
                task_list_to_save.task_list_id,
                status,
                task_list_to_save.state,
            )

        # Status action
        if action == "status":
            logger.info("Returning status for tasklist id=%s", task_list.task_list_id)
            return task_list.to_json(indent=2)

        # Reject action (only at beginning; no tasks should be completed)
        if action == "reject":
            reason = (cmd.get("reason") or "Tasklist rejected by supervisor").strip()
            any_completed = any(t.state == TASK_STATE_COMPLETED for t in task_list.tasks())
            if any_completed:
                logger.warning(
                    "Reject requested but tasks already completed tasklist id=%s",
                    task_list.task_list_id,
                )
                return (
                    "[AutomationProcessor] Cannot reject: some tasks are already completed. "
                    "Return the tasklist to the user for revision instead."
                )

            context.data = context.data or {}
            context.data["agreed"] = False
            context.data["rejected_reason"] = reason
            context.data["tasklist_status"] = "rejected"
            context.data["agreed_at"] = _now_utc().isoformat()
            context.data["agreed_by"] = agent_name
            context.updated_at = _now_utc()
            self.storage.save_context(context)

            logger.info("Tasklist rejected id=%s reason=%s", task_list.task_list_id, reason)
            return task_list.to_json(indent=2)

        if action not in {"run", "resume"}:
            logger.warning("Unknown action=%s", action)
            return f"[AutomationProcessor] Unknown action '{action}'. Supported: status, run, resume, reject."

        # Enforce agreed gate (source of truth is context.data['agreed'])
        agreed = bool((context.data or {}).get("agreed", False))
        if not agreed:
            any_completed = any(t.state == TASK_STATE_COMPLETED for t in task_list.tasks())
            logger.info(
                "Tasklist not agreed (context gate) id=%s any_completed=%s",
                task_list.task_list_id,
                any_completed,
            )
            if not any_completed:
                return (
                    "[AutomationProcessor] Tasklist is not marked agreed in context. "
                    "Ask the user to approve it (set context.data['agreed']=true) "
                    "or send {\"action\":\"reject\",\"reason\":...}.\n\n"
                    + task_list.to_json(indent=2)
                )
            return (
                "[AutomationProcessor] Tasklist not agreed in context but has completed tasks; "
                "returning current state for user review.\n\n" + task_list.to_json(indent=2)
            )

        # Ensure task list is in a sensible starting state
        if task_list.state in {TASK_LIST_STATE_CREATED}:
            task_list.state = TASK_LIST_STATE_RUNNING

        # Mark context as running
        context.data = context.data or {}
        context.data["tasklist_status"] = "running"
        context.updated_at = _now_utc()
        self.storage.save_context(context)
        logger.debug("Context marked running")

        persist(task_list, status="running")

        # Process each pending task in order; persist after each task.
        for task in task_list.tasks():
            if task.state != TASK_STATE_PENDING:
                continue

            logger.info(
                "Running task tasklist_id=%s task_id=%s",
                task_list.task_list_id,
                task.task_id,
            )
            logger.debug("Task description preview: %s", _safe_preview(task.description, 800))

            try:
                worker_result = worker_processor.process_message(
                    primary_agent=secondary_agent,
                    account=account,
                    message=task.description,
                    conversation_id=conversation_id,
                    context_name=context_name,
                )
            except Exception as e:
                logger.exception(
                    "Worker execution failed tasklist_id=%s task_id=%s",
                    task_list.task_list_id,
                    task.task_id,
                )
                # Persist failure info but do not mark task completed.
                task_list.set_task_result(task_id=task.task_id, result=f"Worker error: {e}")
                persist(task_list, status="running")
                return (
                    "[AutomationProcessor] Worker failed on a task. "
                    "Returning tasklist with progress; restart will resume at the failed task.\n\n"
                    + task_list.to_json(indent=2)
                )

            task_list.set_task_result(
                task_id=task.task_id,
                result=worker_result,
                new_state=TASK_STATE_COMPLETED,
            )
            persist(task_list, status="running")
            logger.info(
                "Completed task tasklist_id=%s task_id=%s",
                task_list.task_list_id,
                task.task_id,
            )

        # Mark completed only if all tasks are completed
        all_completed = all(t.state == TASK_STATE_COMPLETED for t in task_list.tasks())
        if all_completed:
            task_list.state = TASK_LIST_STATE_COMPLETED
            persist(task_list, status="completed")

            context.data = context.data or {}
            context.data["tasklist_status"] = "completed"
            context.updated_at = _now_utc()
            self.storage.save_context(context)

            logger.info("Tasklist completed id=%s", task_list.task_list_id)
        else:
            logger.info("Tasklist not fully completed id=%s", task_list.task_list_id)

        updated_task_list_json = task_list.to_json(indent=2)

        if store_this_call:
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="user",
                    content=message,
                    metadata={"agent": agent_name, "account_id": account_name},
                ),
            )
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="assistant",
                    content=updated_task_list_json,
                    metadata={
                        "agent": agent_name,
                        "account_id": account_name,
                        "worker": worker_name,
                        "context_name": context_name,
                    },
                ),
            )

        logger.info(
            "AutomationProcessor end tasklist_id=%s state=%s",
            task_list.task_list_id,
            task_list.state,
        )
        return updated_task_list_json
