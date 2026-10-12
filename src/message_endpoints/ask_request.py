"""Shared /ask payload normalization, required fields and execution lineage."""

from dataclasses import dataclass
import logging
from typing import Any, Dict

from src.execution_identity import ExecutionIdentity


@dataclass(frozen=True)
class AskRequest:
    question: Any
    agent_name: str
    account_name: str
    context_type: Any
    conversation_id: Any
    partner_agent_name: str
    image_ids: Any
    file_ids: Any
    context_name: Any


def parse_request(payload: Dict[str, Any]) -> AskRequest:
    context_name = payload.get("contextName")
    if context_name is not None:
        context_name = str(context_name).strip() or None
    return AskRequest(
        question=payload.get("question", ""),
        agent_name=(payload.get("agentName", "") or "").lower(),
        account_name=(payload.get("accountName", "") or "").lower(),
        context_type=payload.get("selectType", "") or payload.get("contextType", ""),
        conversation_id=payload.get("conversationId", ""),
        partner_agent_name=(payload.get("partnerAgentName", "") or "").lower(),
        image_ids=payload.get("image_ids"),
        file_ids=payload.get("file_ids"),
        context_name=context_name,
    )


def missing_required_fields(request: AskRequest) -> bool:
    return not request.question or not request.agent_name or not request.account_name


def _execution_identity(payload: Dict[str, Any]) -> ExecutionIdentity:
    """Use remote lineage when valid, but always mint the local run ID."""
    trace = payload.get("executionTrace")
    if isinstance(trace, dict):
        try:
            return ExecutionIdentity.remote_child(
                trace_id=trace["trace_id"],
                parent_run_id=trace["parent_run_id"],
            )
        except (KeyError, TypeError, ValueError):
            logging.warning("/ask: invalid remote execution lineage; starting a new trace")
    return ExecutionIdentity.root(message_id=payload.get("messageId"))
