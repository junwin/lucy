"""Execute and interpret one automation task, without changing task states.

The coordinator owns checkpoints, iteration and stop decisions. This component
returns the existing result/error/metrics fields, including partial results on
mandatory stops. Clock and stop detection are supplied by the coordinator.
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any, Callable, NamedTuple, Optional, TYPE_CHECKING

from src.message_processors.automation_inputs import build_task_input

if TYPE_CHECKING:
    from src.agent import Agent
    from src.execution_identity import ExecutionIdentity
    from src.tasklists.task import Task
    from src.tasklists.task_list import TaskList

logger = logging.getLogger(__name__)


class MandatoryStopError(Exception):
    """Raised when a task's model response indicates incomplete work.

    AutomationProcessor treats this as a hard stop: the current task is marked
    failed/error and the tasklist run is terminated.
    """


class TaskExecutionOutcome(NamedTuple):
    result: Optional[dict]
    error: Optional[str]
    metrics: Optional[dict]
    error_detail: Optional[str]


def execute_task(
    *,
    tasklist: TaskList,
    task: Task,
    tasklist_id: str,
    last_task_name: str,
    mode: str,
    function_processor: Any,
    task_agent: Agent,
    account: dict,
    conversation_id: str,
    effective_context: str,
    secondary_agent: Optional[Agent],
    processor_factory: Any,
    child_identity: Optional[ExecutionIdentity],
    correlation_id: Optional[str],
    trace_id: Optional[str],
    warning_messages: list[str],
    now: Callable[[], datetime],
    is_mandatory_stop: Callable[[str], bool],
) -> TaskExecutionOutcome:
    """Attempt the worker once; collect failures without persisting or retrying."""
    # Execute the task using the FunctionCallingProcessor if available;
    # otherwise attach a placeholder result.
    task_result = None
    task_error = None
    run_metrics = None
    error_detail = None
    try:
        if function_processor is not None:
            task_input = build_task_input(tasklist, task)
            task_message = task_input.message
            file_ids = task_input.file_ids
            image_ids = task_input.image_ids
            if not task_message:
                warning_messages.append(
                    f"Task '{last_task_name}' has no instructions; marking completed with warning."
                )
                task_result = {
                    "timestamp": now().isoformat(),
                    "warning": "Task has no instructions. Provide task.instructions to execute.",
                }
            else:
                fcp_result = function_processor.process_message(
                    primary_agent=task_agent,
                    account=account,
                    message=task_message,
                    conversation_id=conversation_id,
                    context_name=effective_context,
                    secondary_agent=secondary_agent,
                    processor_factory=processor_factory,
                    image_ids=image_ids,
                    file_ids=file_ids,
                    correlation_id=(child_identity.run_id if child_identity else correlation_id),
                    trace_id=(child_identity.trace_id if child_identity else trace_id),
                )

                response = fcp_result.text
                run_metrics = fcp_result.metrics.to_dict()
                task_result = {"timestamp": now().isoformat(), "output": response}

                if is_mandatory_stop(response):
                    logger.error(
                        "AutomationProcessor: mandatory-stop response detected for task=%s tasklist_id=%s; aborting",
                        last_task_name,
                        tasklist_id,
                    )
                    raise MandatoryStopError(
                        "Model reported it could not complete the task "
                        f"(internal limit / incomplete response). Aborting tasklist run for task '{last_task_name}'."
                    )
        else:
            task_result = {
                "timestamp": now().isoformat(),
                "note": "Placeholder result. External tool execution disabled for Part 1+2.",
                "intended_action": {"task": last_task_name, "mode": mode},
            }
    except MandatoryStopError as e:
        logger.error("Task execution aborted (mandatory stop) for task=%s: %s", last_task_name, e)
        task_error = str(e)
    except Exception as e:
        logger.exception("Task execution failed for task=%s", last_task_name)
        task_error = str(e)
        error_detail = traceback.format_exc()

    return TaskExecutionOutcome(task_result, task_error, run_metrics, error_detail)
