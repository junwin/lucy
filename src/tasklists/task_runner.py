from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.agent import Agent
from src.message_processors.function_calling_processor import ToolHandlerError
from src.message_processors.message_processor_interface import ProcessorFactoryInterface


class PlannedTask(BaseModel):
    """Canonical task schema.

    Design note:
    - `instruction` is the exact text fed to the worker message processor.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    type: str = "task"
    title: str = ""
    agent: str = ""
    instruction: str
    file: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)


class PlannedTaskList(BaseModel):
    """Canonical tasklist schema returned by plan_tasks."""

    model_config = ConfigDict(extra="allow")

    kind: str = "tasklist"
    description: str = ""
    tasks: List[PlannedTask] = Field(default_factory=list)


@dataclass(frozen=True)
class TaskRunnerResult:
    ok: bool
    description: str
    tasks: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "description": self.description, "tasks": self.tasks}


class TaskRunner:
    """Execute a "simple tasklist" returned by the plan_tasks tool.

    Design note:
    - We keep FunctionCallingProcessor focused on model/tool orchestration for a single
      inbound message.
    - Auto-run of plan_tasks is preserved, but the execution of the resulting tasklist
      is owned by the /ask request flow (AskRequestHandler) via this TaskRunner.
    """

    def __init__(self, *, processor_factory: ProcessorFactoryInterface) -> None:
        self.processor_factory = processor_factory
        self.logger = logging.getLogger(__name__)

    def run(
        self,
        *,
        tasklist: Dict[str, Any] | PlannedTaskList,
        supervisor_agent: Agent,
        worker_agent: Optional[Agent],
        account: Dict[str, Any],
        conversation_id: str,
        context_name: str,
    ) -> Dict[str, Any]:
        max_depth = int(getattr(supervisor_agent, "max_delegation_depth", 1))
        delegation_depth = int(getattr(supervisor_agent, "delegation_depth", 0))

        if delegation_depth >= max_depth:
            self.logger.warning(
                "TaskRunner: delegation depth %d >= max %d for agent=%s session_id=%s; refusing.",
                delegation_depth,
                max_depth,
                supervisor_agent.name,
                conversation_id,
            )
            return {"ok": False, "error": "Max delegation depth exceeded while executing the tasklist."}

        try:
            planned = tasklist if isinstance(tasklist, PlannedTaskList) else PlannedTaskList.model_validate(tasklist)
        except ValidationError as e:
            return {"ok": False, "error": f"Invalid tasklist schema: {e}"}

        self.logger.info(
            "TaskRunner: start supervisor=%s worker=%s session_id=%s tasks=%d depth=%d/%d desc=%r",
            supervisor_agent.name,
            worker_agent.name if worker_agent else None,
            conversation_id,
            len(planned.tasks),
            delegation_depth,
            max_depth,
            planned.description[:120],
        )

        # Use worker's configured processor (typically FunctionCallingProcessor)
        worker_processor = None
        if worker_agent is not None:
            worker_processor_name = (worker_agent.message_processor or "").strip()
            if worker_processor_name:
                worker_processor = self.processor_factory.get(worker_processor_name)

        results: List[Dict[str, Any]] = []

        for idx, task in enumerate(planned.tasks, start=1):
            task_id = task.id or f"task-{idx}"
            task_type = task.type or "task"
            task_agent_name = task.agent or (worker_agent.name if worker_agent else "")
            task_title = task.title or ""
            instruction = task.instruction or ""
            file_path = task.file or ""

            self.logger.info(
                "TaskRunner: task %d/%d id=%s type=%s agent=%s title=%r",
                idx,
                len(planned.tasks),
                task_id,
                task_type,
                task_agent_name,
                task_title[:80],
            )

            if task_type != "task":
                results.append({"id": task_id, "ok": False, "error": f"Unsupported task type: {task_type}"})
                continue

            if not instruction:
                results.append({"id": task_id, "ok": False, "error": "Task has no instruction to execute."})
                continue

            msg_parts = [instruction]
            if file_path:
                msg_parts.append(f"\n\nFocus file: {file_path}")
            task_message = "".join(msg_parts)

            if worker_agent is None or task_agent_name != worker_agent.name:
                results.append(
                    {"id": task_id, "ok": False, "agent": task_agent_name, "error": f"Unknown agent: {task_agent_name}"}
                )
                continue

            if worker_processor is None:
                results.append({"id": task_id, "ok": False, "agent": task_agent_name, "error": "Worker agent has no message_processor."})
                continue

            try:
                task_response = worker_processor.process_message(
                    primary_agent=worker_agent,
                    account=account,
                    message=task_message,
                    conversation_id=conversation_id,
                    context_name=context_name,
                    secondary_agent=None,
                    processor_factory=self.processor_factory,
                )
                results.append({"id": task_id, "ok": True, "agent": task_agent_name, "response": task_response})
            except ToolHandlerError as e:
                self.logger.exception("TaskRunner: error executing worker task id=%s", task_id)
                results.append({"id": task_id, "ok": False, "agent": task_agent_name, "error": f"{type(e).__name__}: {e}"})
                break

        summary = TaskRunnerResult(
            ok=all(r.get("ok") for r in results) if results else False,
            description=planned.description,
            tasks=results,
        ).to_dict()

        self.logger.info(
            "TaskRunner: completed supervisor=%s worker=%s session_id=%s tasks=%d ok=%s",
            supervisor_agent.name,
            worker_agent.name if worker_agent else None,
            conversation_id,
            len(results),
            summary["ok"],
        )

        return summary
