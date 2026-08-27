from dataclasses import dataclass
import logging
from typing import Optional, Dict, Any

from src.agent import Agent
from galet.provider_registry import ProviderRegistry


class ToolResultTooLargeError(Exception):
    """Raised when a tool result exceeds the configured max_tool_result_chars."""


class ToolHandlerError(Exception):
    """Raised when a tool handler fails during execution."""


# Default cap for the handler-schema token guardrail (overridable via the config
# key 'max_handler_schema_tokens').
DEFAULT_MAX_HANDLER_SCHEMA_TOKENS = 8000


@dataclass(frozen=True)
class ProcessorContext:
    account_id: str
    agent_name: str
    conversation_id: str
    context_name: str
    model: str
    temperature: float
    context_type: str
    max_iterations: int
    store_this_call: bool
    delegation_depth: int
    provider: Optional[str] = None

    @classmethod
    def from_agent(
        cls,
        *,
        primary_agent: Agent,
        account: Dict[str, Any],
        conversation_id: str,
        context_name: str,
    ) -> "ProcessorContext":
        account_id = (account.get("accountId") or "").strip()
        agent_name = primary_agent.name or "unknown"

        max_iterations = int(primary_agent.max_function_call_iterations or 10)
        if max_iterations <= 0:
            logging.warning(
                "max_function_call_iterations for agent '%s' is %d; using 1 instead",
                agent_name,
                max_iterations,
            )
            max_iterations = 1

        # Resolve provider name if agent has explicit provider; otherwise None.
        provider_explicit = getattr(primary_agent, "provider", None)
        if provider_explicit:
            try:
                provider = ProviderRegistry.resolve_name(primary_agent.model, provider_explicit)
            except ValueError:
                logging.warning(
                    "FCP: unknown provider '%s' for agent '%s', ignoring",
                    provider_explicit,
                    agent_name,
                )
                provider = None
        else:
            provider = None

        resolved_context_name = context_name or ""
        if not resolved_context_name.strip() and primary_agent.default_context:
            resolved_context_name = str(primary_agent.default_context).strip()

        return cls(
            account_id=account_id,
            agent_name=agent_name,
            conversation_id=conversation_id,
            context_name=resolved_context_name,
            model=primary_agent.model,
            temperature=primary_agent.temperature,
            context_type=primary_agent.context_type or "hybrid",
            max_iterations=max_iterations,
            store_this_call=bool(primary_agent.save_responses),
            delegation_depth=int(getattr(primary_agent, "delegation_depth", 0)),
            provider=provider,
        )


@dataclass
class RequestContext:
    """Per-run accumulator for correlation-scoped ERROR/WARNING counts.

    Registered with CorrelationLogHandler while a run is active; the handler
    increments the counters as matching log records are emitted.
    """

    correlation_id: str
    errors: int = 0
    warnings: int = 0


@dataclass(frozen=True)
class _ToolCall:
    name: str
    call_id: str
    arguments_raw: str
