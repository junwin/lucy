from __future__ import annotations

import json
import logging
from typing import Optional, Any, Dict, Tuple

from injector import inject

from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.agent.agent import Agent
from src.message_processors.types import AccountDict
from src.storage.base import Storage
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_PENDING


logger = logging.getLogger(__name__)


def _parse_json_command(message: str) -> Tuple[Optional[dict], Optional[str]]:
    raw = (message or "").strip()
    if not raw:
        return None, None

    try:
        obj = json.loads(raw)
    except Exception:
        return None, "Invalid JSON command"

    if not isinstance(obj, dict):
        return None, "JSON command must be an object"

    return obj, None


def _find_next_pending_task(tasklist: TaskList) -> Tuple[Optional[int], Optional[Any]]:
    tasks = getattr(tasklist, "tasks", None) or []
    for idx, task in enumerate(tasks):
        state = getattr(task, "state", None)
        if state == TASK_STATE_PENDING:
            return idx, task
    return None, None


class TaskRunningProcessor(MessageProcessorInterface):
    """Task running processor: Step 3.2 behavior.

    Responsibilities for this step:
    - Parse a JSON command like {"action": "run", "tasklist_id": "...", "mode": "single-step"}
    - Determine execution mode (single-step|multi-step)
    - Select the next Pending task from the persisted tasklist
    - Do not execute the task yet
    """

    @inject
    def __init__(self, storage: Optional[Storage] = None) -> None:
        # Storage is optional for test convenience; production injector will
        # provide a Storage implementation.
        self.storage = storage

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
        agent_name = (getattr(primary_agent, "name", "") or "").lower().strip()
        if agent_name != "doris":
            logger.debug("TaskRunningProcessor ignoring agent=%s", agent_name)
            return f"[TaskRunningProcessor] Not responsible for agent '{agent_name}'."

        if not context_name:
            logger.warning("TaskRunningProcessor missing context_name")
            return "[TaskRunningProcessor] Missing context_name."

        cmd, err = _parse_json_command(message)
        if err:
            return f"[TaskRunningProcessor] {err}"

        if not cmd:
            return (
                "[TaskRunningProcessor] This processor expects a JSON command. "
                "Example: {\"action\": \"run\", \"tasklist_id\": \"my_tasklist_1\", \"mode\": \"multi-step\"}."
            )

        action = str(cmd.get("action") or "").lower().strip()
        if action not in {"run", "execute", "start"}:
            return "[TaskRunningProcessor] Unknown action. Use 'run'"

        tasklist_id = str(cmd.get("tasklist_id") or "").strip()
        if not tasklist_id:
            return "[TaskRunningProcessor] Missing required field 'tasklist_id'."

        mode = str(cmd.get("mode") or "").strip() or "single-step"
        if mode not in {"single-step", "multi-step"}:
            return "[TaskRunningProcessor] Invalid mode. Use 'single-step' or 'multi-step'."

        account_name = (account.get("accountId") or "").strip() or "(missing accountId)"

        if not self.storage:
            return (
                "[TaskRunningProcessor] No storage configured. In tests, provide a storage via injector."
            )

        try:
            raw = self.storage.get_tasklist(account_name, tasklist_id)
        except Exception as e:
            logger.exception("Failed loading tasklist from storage")
            return f"[TaskRunningProcessor] Failed to load tasklist: {e}"

        if not raw:
            return f"[TaskRunningProcessor] tasklist={tasklist_id} not found"

        # coerce to TaskList
        try:
            if isinstance(raw, dict):
                tasklist = TaskList.from_dict(raw, id=raw.get("id") or tasklist_id)
            elif isinstance(raw, str):
                tasklist = TaskList.from_json(raw)
            else:
                return "[TaskRunningProcessor] Unsupported persisted tasklist format"
        except Exception as e:
            logger.exception("Failed parsing persisted tasklist")
            return f"[TaskRunningProcessor] Failed to parse stored tasklist: {e}"

        idx, task = _find_next_pending_task(tasklist)
        if task is None:
            return f"[TaskRunningProcessor] mode={mode} no pending tasks"

        task_name = getattr(task, "title", None) or getattr(task, "name", None) or f"task#{idx}"
        return f"[TaskRunningProcessor] mode={mode} next_task_index={idx} next_task_name='{task_name}'"
