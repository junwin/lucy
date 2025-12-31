from typing import Optional

from injector import inject
import logging
from typing import Optional, Dict, Any

import json

from src.config_manager import ConfigManager
#from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_processors.message_processor_interface import MessageProcessorInterface
#from src.message_processors.processor_factory import ProcessorFactory
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.message_processors.types import AgentDict, AccountDict
from src.api_helpers import openai_call, ToolResult
from src.handlers.handler_registry import HandlerRegistry
from src.storage.base import Storage 
from src.storage.models import ChatMessage

from src.tasklists.file_tasklist import FileTaskList
from src.tasklists.tasklist_interface import (
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_LIST_STATE_COMPLETED,
    TASK_STATE_PENDING,
    TASK_STATE_COMPLETED,
)

logger = logging.getLogger(__name__)


class AutomationProcessor(MessageProcessorInterface):
    """Automation processor for running simple task lists.

    Current behaviour (MVP):
    - Only handles the supervisor agent "doris".
    - Expects `message` to be a JSON-encoded task list (the whole string).
    - Parses the task list, runs each pending task via a worker assistant,
      updates task states/results, and returns the updated task list JSON.
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
        self.context_type = ""
        self.prompt_builder = prompt_builder

    def process_message(
        self,
        *,
        primary_agent: AgentDict,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[AgentDict] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        agent_name = (primary_agent.get("name") or "").lower().strip()
        if agent_name != "doris":
            return f"[AutomationProcessor] Not responsible for agent '{agent_name}'."

        store_this_call = bool(primary_agent.get("save_reposnses", False))

        account_id = (account.get("accountId") or "").strip() or "(missing accountId)"
        worker_name = (
            (secondary_agent or {}).get("name")
            or (primary_agent.get("partner_agent") or "")
            or "billy"
        )
        worker_name = worker_name.lower().strip()
        worker_processor = processor_factory.get("function_calling_processor") if processor_factory else None   
        
        # 1. Parse the incoming message as a JSON task list
        try:
            # message is the JSON string for the task list
            # We parse it once to validate it's JSON, then pass it to FileTaskList
            json.loads(message)  # just to validate
            task_list = FileTaskList.from_json(message)
        except json.JSONDecodeError:
            error_text = (
                "[AutomationProcessor] Expected JSON task list in message, "
                "but could not parse JSON."
            )
            logger.warning(error_text)
            return error_text
        except Exception as e:
            logger.exception("Failed to parse task list JSON")
            return f"[AutomationProcessor] Failed to parse task list JSON: {e}"

        # 2. Ensure task list is in a sensible starting state
        if task_list.state == TASK_LIST_STATE_CREATED:
            task_list.state = TASK_LIST_STATE_RUNNING
        else:
            logger.info(
                "AutomationProcessor received task list in state %s (id=%s)",
                task_list.state,
                task_list.task_list_id,
            )

        # 3. Process each pending task in order
        for task in task_list.tasks():
            if task.state != TASK_STATE_PENDING:
                continue

            try:
                worker_result = worker_processor.process_message(
                    primary_agent=secondary_agent,
                    account=account,
                    message=task.description,
                    conversation_id=conversation_id,
                    context_name=context_name,
                ) 
                #worker_result = self._run_worker_for_task(
                #    worker_name=worker_name,
                 #   account=account,
                 #   conversation_id=conversation_id,
                   # task_text=task.description,
                #)
            except Exception as e:
                logger.exception("Worker execution failed for task %s", task.task_id)
                worker_result = f"Worker error: {e}"

            task_list.set_task_result(
                task_id=task.task_id,
                result=worker_result,
                new_state=TASK_STATE_COMPLETED,
            )

        # 4. Mark the overall task list as completed (MVP behaviour)
        task_list.state = TASK_LIST_STATE_COMPLETED

        # 5. Serialise the updated task list back to JSON
        updated_task_list_json = task_list.to_json(indent=2)

        # 6. Optionally store the original message and the updated task list
        if store_this_call:
            # Store the original incoming message
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="user",
                    content=message,
                    metadata={"agent": agent_name, "account_id": account_id},
                ),
            )
            # Store the updated task list as the assistant's response
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="assistant",
                    content=updated_task_list_json,
                    metadata={
                        "agent": agent_name,
                        "account_id": account_id,
                        "worker": worker_name,
                    },
                ),
            )

        # 7. Return the updated task list JSON as the response
        return updated_task_list_json

    # ------------------------------------------------------------------
    # Worker integration (MVP stub)
    # ------------------------------------------------------------------

    def _run_worker_for_task(
        self,
        *,
        worker_name: str,
        account: AccountDict,
        conversation_id: str,
        task_text: str,
    ) -> str:
        """Placeholder for calling a worker assistant.

        For now this is a stub that just echoes the task text.
        Later this should:
        - look up the worker agent config by name,
        - build a prompt using prompt_builder,
        - call the model/tooling,
        - and return the worker's response text.
        """
        logger.info(
            "AutomationProcessor would call worker '%s' for conversation %s with task: %s",
            worker_name,
            conversation_id,
            task_text,
        )
        return f"[worker:{worker_name}] processed task: {task_text}"
