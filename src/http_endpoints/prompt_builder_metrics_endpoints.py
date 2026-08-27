"""Metrics endpoint for prompt builder token accounting.

Provides a /prompt_builder/metrics route that builds the exact same prompt
as /prompt_builder but also returns:
  - PromptBuilder._last_prompt_token_breakdown (internal accounting snapshot
    taken after chat-history selection)
  - a per-message token/char table with previews
  - the sum of per-message token estimates (total_tokens_actual)
  - the tool handler schema set that would be sent to the model (filtered by
    the agent's allowed_tools, same as FunctionCallingProcessor), plus its
    token cost (handler_schema_tokens) and a per-handler table

This is a read-only diagnostic tool — it does not modify any state.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

from src.handlers.handler_registry import HandlerRegistry
from src.prompt_builders.prompt_builder import PromptBuilder, estimate_tokens_from_text
from src.message_processors.function_calling_processor import (
    apply_handler_schema_budget,
    load_context_state,
    resolve_handler_schema_cap,
    resolve_tool_defs,
)


def _handler_schema_metrics(
    function_defs: List[Dict[str, Any]],
) -> Tuple[int, List[Dict[str, Any]]]:
    """Return (total_tokens, per_handler_table) for a list of tool defs.

    total_tokens is computed from the serialized JSON array exactly as it would
    be sent to the model. Per-handler tokens are informational and may not sum
    exactly to total_tokens due to array/object framing characters.
    """
    handlers_table: List[Dict[str, Any]] = []
    for fd in function_defs:
        text = json.dumps(fd, ensure_ascii=False)
        handlers_table.append({
            "name": fd.get("name", ""),
            "tokens": estimate_tokens_from_text(text),
            "chars": len(text),
            "preview": text[:120],
        })

    handlers_text = json.dumps(function_defs, ensure_ascii=False)
    total_tokens = estimate_tokens_from_text(handlers_text)
    return total_tokens, handlers_table


def prompt_builder_metrics_impl(
    agent_manager,
    storage,
    container,
    config,
    payload: dict,
) -> Tuple[Any, int]:
    """Build the prompt like /prompt_builder and return token metrics.

    Returns 200 with:
      - agent/account/context_type/conversation_id echo
      - message_count
      - breakdown: PromptBuilder._last_prompt_token_breakdown, enriched with
        tool_handler_schemas and total_with_handlers
      - total_tokens_actual: sum of per-message token estimates
      - messages: [{index, role, tokens, chars, preview}, ...]
      - handler_schema_tokens: token cost of the tool handler schema set
      - handlers: [{name, tokens, chars, preview}, ...]

    On exception returns {"error": str(e)}, 500.
    """
    # --- Validate payload exactly like build_prompt_impl ---
    question = payload.get("query", "")
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    # keep request field name for now, but map to context_type
    context_type = payload.get("selectType", "") or payload.get("contextType", "")
    conversationId = payload.get("conversationId", "")

    # Optional: None means "no storage-based context"
    context_name = payload.get("contextName") or payload.get("context_name")
    if context_name is not None:
        context_name = str(context_name).strip() or None

    # allow optional list of extra system messages
    extra_system_messages = payload.get("extraSystemMessages") or ["my system Message"]
    if not isinstance(extra_system_messages, list):
        extra_system_messages = [str(extra_system_messages)]

    if not question or not agentName or not accountName:
        return {"error": "Missing query, agentName, or accountName"}, 400

    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    my_agent = agent_manager.get_agent(agentName)
    if not context_type:
        # default from agent config
        context_type = my_agent.context_type if my_agent else "hybrid"

    try:
        # PromptBuilder is DI-based and requires agent_manager/config/storage.
        # Resolve it from the container (preferred) or construct with deps.
        prompt_builder = container.get(PromptBuilder)
    except Exception:
        prompt_builder = PromptBuilder(agent_manager=agent_manager, config=config, storage=storage)

    # --- Resolve tool handler schema set (same source as the FCP) ---
    try:
        registry = container.get(HandlerRegistry)
    except Exception:
        registry = None

    try:
        prompt = prompt_builder.build_prompt(
            content_text=question,
            conversation_id=conversationId,
            agent_name=agentName,
            account_name=accountName,
            context_type=context_type,
            max_prompt_chars=payload.get("maxPromptChars", 6000),
            context_name=context_name,
            extra_system_messages=extra_system_messages,
        )

        # --- Per-message token table ---
        messages_table: List[Dict[str, Any]] = []
        total_tokens_actual = 0
        for i, msg in enumerate(prompt):
            content = msg.get("content")
            content_str = content if isinstance(content, str) else str(content)
            tokens = estimate_tokens_from_text(content_str)
            chars = len(content_str)
            total_tokens_actual += tokens
            messages_table.append({
                "index": i,
                "role": msg.get("role", ""),
                "tokens": tokens,
                "chars": chars,
                "preview": content_str[:80],
            })

        # --- Tool handler schema metrics ---
        # Use the FCP's resolve_tool_defs (single source of truth) so the
        # metrics endpoint reports the exact same tool set the FCP would send.
        # The active context may carry an optional non-empty tool list
        # (Context.extra['allowed_tools']) clamped by the agent's
        # allowed_tools (hard ceiling). Missing/empty => no restriction.
        context_state = load_context_state(prompt_builder, accountName, context_name)
        filtered_function_defs = resolve_tool_defs(registry, my_agent, context_state) if registry is not None else []
        # Apply the same handler-schema budget guardrail the FCP applies, so the
        # reported tool set matches exactly what the FCP would send to the model.
        filtered_function_defs = apply_handler_schema_budget(
            filtered_function_defs,
            config,
            agent_name=agentName,
        )
        handler_tokens, handlers_table = _handler_schema_metrics(filtered_function_defs)

        breakdown = dict(prompt_builder._last_prompt_token_breakdown or {})
        total_without_handlers = int(breakdown.get("total_without_handlers", 0))
        breakdown["tool_handler_schemas"] = handler_tokens
        breakdown["total_with_handlers"] = total_without_handlers + handler_tokens

        result = {
            "agent": agentName,
            "account": accountName,
            "context_type": context_type,
            "conversation_id": conversationId,
            "message_count": len(prompt),
            "breakdown": breakdown,
            "total_tokens_actual": total_tokens_actual,
            "handler_schema_tokens": handler_tokens,
            "handler_schema_cap": resolve_handler_schema_cap(config),
            "tool_count": len(filtered_function_defs),
            "handlers": handlers_table,
            "messages": messages_table,
        }
        return result, 200
    except Exception as e:
        logging.exception("Error in /prompt_builder/metrics")
        return {"error": str(e)}, 500
