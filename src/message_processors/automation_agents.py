"""Agent and context selection for automation, without execution or persistence.

The coordinator supplies its current AgentManager explicitly; this module does
not retain processor state or import the coordinator.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agent import Agent
    from src.agent.agent_manager import AgentManager
    from src.tasklists.task import Task

logger = logging.getLogger(__name__)


def resolve_task_agent(
    task: Task,
    primary_agent: Agent,
    agent_name: str,
    secondary_agent: Optional[Agent] = None,
    *,
    agent_manager: Optional[AgentManager] = None,
) -> Agent:
    """Resolve the agent to use for executing a task.

    task.agent set and differing from the caller must resolve via AgentManager
    or ValueError is raised. task.agent matching the caller uses the caller.
    task.agent unset uses the caller's partner (secondary_agent, else the
    caller's configured partner_agent) when available, else the caller.

    Returns the resolved Agent to use for this task.
    """
    task_agent_name = (task.agent or "").strip().lower()
    caller_name = (agent_name or "").strip().lower()

    if task_agent_name:
        if task_agent_name == caller_name:
            logger.info(
                "AutomationProcessor: task '%s' agent=%s (same as caller=%s), using primary agent",
                task.name,
                task_agent_name,
                caller_name,
            )
            return primary_agent

        logger.info(
            "AutomationProcessor: task '%s' requested agent=%s, caller=%s — resolving worker agent",
            task.name,
            task_agent_name,
            caller_name,
        )

        if agent_manager is not None:
            worker = agent_manager.get_agent(task_agent_name)
            if worker is not None:
                logger.info(
                    "AutomationProcessor: resolved worker agent '%s' for task '%s'",
                    task_agent_name,
                    task.name,
                )
                return worker

        raise ValueError(
            f"task agent '{task_agent_name}' not found (task '{task.name}')"
        )

    partner: Optional[Agent] = None
    if secondary_agent is not None:
        partner = secondary_agent
    else:
        partner_name = (
            getattr(primary_agent, "partner_agent", None) or ""
        ).strip().lower()
        if partner_name and agent_manager is not None:
            partner = agent_manager.get_agent(partner_name)
        if partner_name and partner is None:
            logger.warning(
                "AutomationProcessor: partner agent '%s' of caller '%s' not resolvable; treating as no partner",
                partner_name,
                caller_name,
            )

    if partner is not None:
        logger.info(
            "AutomationProcessor: task '%s' agent unset; using partner agent '%s'",
            task.name,
            (getattr(partner, "name", "") or "").lower().strip(),
        )
        return partner

    logger.info(
        "AutomationProcessor: task '%s' agent=%s (none, no partner), using primary agent",
        task.name,
        "(none)",
    )
    return primary_agent


def resolve_worker_agent(
    worker_agent: Optional[str], agent_manager: Optional[AgentManager]
) -> tuple[Optional[Agent], Optional[str]]:
    """Resolve the run override before loading or mutating a tasklist."""
    resolved_worker: Optional[Agent] = None
    resolved_worker_name: Optional[str] = None
    if worker_agent:
        worker_name = worker_agent.strip().lower()
        if agent_manager is not None:
            resolved_worker = agent_manager.get_agent(worker_name)
        if resolved_worker is None:
            raise ValueError(f"worker agent '{worker_name}' not found")
        resolved_worker_name = (
            getattr(resolved_worker, "name", "") or ""
        ).lower().strip()
        logger.info(
            "execute_tasklist: using worker agent '%s' for all tasks",
            resolved_worker_name,
        )
    return resolved_worker, resolved_worker_name


def resolve_task_context(
    context_name: Optional[str], task: Task, task_agent: Agent
) -> str:
    """Preserve run override > task context > agent default precedence.

    A nonempty run override is returned verbatim, including whitespace.
    """
    effective_context = context_name or ""
    if not effective_context:
        effective_context = (task.context or "").strip()
    if not effective_context:
        effective_context = (
            getattr(task_agent, "default_context", None) or ""
        ).strip()
    return effective_context
