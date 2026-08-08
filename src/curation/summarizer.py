"""LLM-based summarization for curation digest mode.

Takes session events and asks the LLM to distill them into a structured
Markdown digest.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.chat2.models import ChatEvent
from src.llm.dto import LLMResponse
from src.llm.interface import LLMApi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for summarization
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = """You are a chat session summarizer. Your job is to distill a conversation into a structured Markdown digest.

First, scan the entire conversation and identify all distinct topic clusters. These could be:
- Code/config changes (file edits, tool outputs, test results)
- Design discussions or architectural decisions
- Creative or analytical conversations (poetry, books, ideas, comparisons, opinions)
- Problem-solving threads (debugging, troubleshooting)
- Meta-discussion about process or workflow

Then produce a digest that covers ALL clusters proportionally. Do NOT drop a topic just because it is "subjective" or "not actionable." A poetry discussion or casual exchange is just as important as a file save. Represent what actually happened, not just what produced artifacts.

Output format (Markdown):

## Topics discussed
- Brief summary of each distinct topic cluster in the conversation

## Decisions made
- ...

## Files created/modified
- ...

## Key outcomes
- ...

## Open questions / next steps
- ...

If a section has no content, write "None." for that section."""


def _build_events_text(events: List[ChatEvent], max_chars: int = 32000) -> str:
    """Build a text representation of events for the LLM.

    Truncates to max_chars to avoid blowing the context window.
    """
    lines: List[str] = []
    total = 0

    for e in events:
        payload_str = (
            json.dumps(e.payload, ensure_ascii=False)
            if isinstance(e.payload, dict)
            else str(e.payload)
        )
        line = f"[{e.ts.isoformat()}] {e.role}/{e.actor} ({e.kind}): {payload_str[:500]}"
        total += len(line) + 1
        if total > max_chars:
            lines.append("... (truncated)")
            break
        lines.append(line)

    return "\n".join(lines)


def summarize_session(
    events: List[ChatEvent],
    *,
    llm_api: LLMApi,
    model: str = "gpt-4o-mini",
    friendly_name: str = "",
    session_id: str = "",
    account: str = "",
    temperature: float = 0.0,
) -> str:
    """Summarize session events into a structured Markdown digest.

    Args:
        events: List of ChatEvent objects to summarize.
        llm_api: LLM API instance.
        model: Model name to use for summarization.
        friendly_name: Session friendly name (for context).
        session_id: Session UUID (for context).
        account: Account name (for context).
        temperature: LLM temperature.

    Returns:
        Structured Markdown digest string.
    """
    events_text = _build_events_text(events)

    user_prompt = f"""Summarize this chat session.

Session: {friendly_name or session_id}
Account: {account}

Conversation events:
{events_text}

Produce a structured Markdown digest with these sections:
- Topics discussed
- Decisions made
- Files created/modified
- Key outcomes
- Open questions / next steps
"""

    messages = [
        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response: LLMResponse = llm_api.create_response(
            model=model,
            input=messages,
            temperature=temperature,
        )
        digest = response.output_text.strip()
        if not digest:
            logger.warning(
                "summarize_session: LLM returned empty output for session=%s — using fallback",
                session_id,
            )
            return _fallback_digest(events, friendly_name=friendly_name, session_id=session_id)
        logger.info(
            "summarize_session: generated digest for session=%s (%d chars)",
            session_id,
            len(digest),
        )
        return digest
    except Exception:
        logger.exception("summarize_session: LLM call failed for session=%s", session_id)
        return _fallback_digest(events, friendly_name=friendly_name, session_id=session_id)


def _fallback_digest(
    events: List[ChatEvent],
    *,
    friendly_name: str = "",
    session_id: str = "",
) -> str:
    """Generate a simple text digest without LLM (fallback)."""
    lines = [f"# Session Digest: {friendly_name or session_id}", ""]
    lines.append("## Events")
    for e in events:
        payload_str = (
            json.dumps(e.payload, ensure_ascii=False)
            if isinstance(e.payload, dict)
            else str(e.payload)
        )
        snippet = payload_str[:200].replace("\n", " ")
        lines.append(f"- **[{e.role}]** ({e.kind}): {snippet}")
    return "\n".join(lines)
