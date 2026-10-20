"""Prompt token accounting and compatibility helpers for the metrics endpoint.

Active tool selection remains owned by ToolSelectionPipeline. The tail-trimming
helper here retains its existing metrics-endpoint behaviour, not a new selector.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from galet_prompt_builder import ApproximateTokenCounter
from src.agent.caps import resolve_effective_cap
from src.handlers.handler_registry import filter_eligible_tool_defs
from src.message_processors.fcp_models import (
    ProcessorContext, DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
)

_TOKEN_COUNTER = ApproximateTokenCounter()


def _compute_prompt_token_breakdown(prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compute token counts for all prompt sections including handler definitions.

    Guarded against Mock objects in tests: if prompt_builder doesn't have a real
    breakdown dict, returns zeros across the board. Handlers use the shared
    _handler_schema_tokens() estimator so all callers agree on the same count.
    """
    pb_breakdown = getattr(prompt_builder, "_last_prompt_token_breakdown", {})
    if isinstance(pb_breakdown, dict):
        system_tokens = pb_breakdown.get("system_session", 0)
        context_tokens = pb_breakdown.get("context_text", 0)
        obsidian_tokens = pb_breakdown.get("obsidian_notes", 0)
        digest_tokens = pb_breakdown.get("digest_embeddings", 0)
        history_tokens = pb_breakdown.get("chat_history", 0)
        user_tokens = pb_breakdown.get("current_user_message", 0)
        total_without_handlers = pb_breakdown.get("total_without_handlers", 0)
    else:
        # Mock or other non-dict — safe zeroes
        system_tokens = context_tokens = obsidian_tokens = digest_tokens = history_tokens = user_tokens = total_without_handlers = 0

    try:
        handler_tokens = _handler_schema_tokens(filtered_function_defs)
    except Exception:
        handler_tokens = 0

    return {
        "system": system_tokens,
        "handlers": handler_tokens,
        "context": context_tokens,
        "obsidian": obsidian_tokens,
        "digest": digest_tokens,
        "history": history_tokens,
        "user": user_tokens,
        "total": total_without_handlers + handler_tokens,
    }


def _log_token_breakdown(ctx: ProcessorContext, prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Measure and log token counts for all prompt sections including handler definitions.

    Calls _compute_prompt_token_breakdown() once and returns the breakdown dict
    so callers can reuse it without recomputing.
    """
    breakdown = _compute_prompt_token_breakdown(prompt_builder, filtered_function_defs)

    logging.info(
        "Prompt.token_breakdown: agent=%s account=%s session=%s system=%d handlers=%d context=%d obsidian=%d digest=%d history=%d user=%d total=%d",
        ctx.agent_name,
        ctx.account_id,
        ctx.conversation_id,
        breakdown["system"],
        breakdown["handlers"],
        breakdown["context"],
        breakdown["obsidian"],
        breakdown["digest"],
        breakdown["history"],
        breakdown["user"],
        breakdown["total"],
    )
    return breakdown


def resolve_tool_defs(registry, agent, context_state: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Resolve the tool definitions the agent is allowed to use.

    Thin wrapper over the shared filter_eligible_tool_defs() helper (the
    same one HandlerRegistry.eligible_tool_defs uses). Kept for backward
    compatibility with existing callers.

    Single source of truth for tool-list resolution across
    process_message(), process_message_streaming(), and the
    /prompt_builder/metrics endpoint.

    See filter_eligible_tool_defs() for the full filtering rules.
    """
    function_defs = registry.tools() if registry is not None else []
    return filter_eligible_tool_defs(function_defs, agent, context_state)


def _handler_schema_tokens(function_defs: List[Dict[str, Any]]) -> int:
    """Estimate schema tokens for a list of tool defs (same estimator as the prompt builder)."""
    if not function_defs:
        return 0
    try:
        text = json.dumps(function_defs, ensure_ascii=False)
    except Exception:
        return 0
    return _TOKEN_COUNTER.count(text)


def apply_handler_schema_budget(
    function_defs: List[Dict[str, Any]],
    config: Any,
    agent: Optional[Any] = None,
    *,
    agent_name: str = "<unknown>",
) -> List[Dict[str, Any]]:
    """Trim tool defs from the tail when schema tokens exceed the configured cap.

    Pure guardrail - never a selection mechanism. Runs AFTER resolution
    (resolve_tool_defs), so it can only remove tools, never add or reorder.

    - Under/at the cap: returns the list unchanged, no log.
    - Over the cap: removes tool defs from the tail until under the cap,
      always keeping at least one def (a single oversized def is kept; trimming
      to zero tools would disable tool use entirely, which is a policy decision
      for allowed_tools, not a token guardrail). Logs a warning with the
      before/after token counts and how many defs were trimmed.
    """
    if not function_defs:
        return function_defs

    cap = resolve_effective_cap("max_handler_schema_tokens", agent, config, DEFAULT_MAX_HANDLER_SCHEMA_TOKENS, disable_on_non_positive=True)
    if cap is None:
        return function_defs

    trimmed = list(function_defs)
    tokens = _handler_schema_tokens(trimmed)
    if tokens <= cap:
        return trimmed

    original_count = len(trimmed)
    original_tokens = tokens
    while len(trimmed) > 1 and tokens > cap:
        trimmed.pop()
        tokens = _handler_schema_tokens(trimmed)

    logging.warning(
        "FunctionCallingProcessor: handler schema tokens=%d exceed cap=%d for agent '%s'; "
        "trimmed %d tool def(s) from the tail (kept %d, tokens=%d)",
        original_tokens,
        cap,
        agent_name,
        original_count - len(trimmed),
        len(trimmed),
        tokens,
    )
    return trimmed
