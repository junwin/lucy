"""
Prompt slicing for Chat v2.

Given a stream of ChatEvents and a max count N, returns the last N
user/assistant events (excluding tool results, tool calls, system notes,
and summaries) in chronological order.

This is the simplest possible slicing strategy — last N conversational
turns. Future strategies (embedding similarity, keyword matching, time-based
relevance) can be added here without changing the caller.
"""

from __future__ import annotations

from typing import Iterable, List

from src.chat2.models import ChatEvent

# Kinds that represent actual conversational turns (user or assistant).
_CONVERSATION_KINDS = frozenset({"user_message", "assistant_message"})


def get_last_n_events(events: Iterable[ChatEvent], n: int) -> List[ChatEvent]:
    """Return the last N user/assistant events from a session.

    Excludes events of kind: tool_result, assistant_tool_call, system_note,
    summary. Returns events in chronological order.

    Args:
        events: An iterable of ChatEvent objects (e.g. from stream_events).
        n: Maximum number of events to return. If n <= 0, returns empty list.

    Returns:
        A list of ChatEvent objects in chronological order, with at most n
        entries. May return fewer than n if the session has fewer matching
        events.
    """
    if n <= 0:
        return []

    # Collect matching events, then take the last N.
    matching = [e for e in events if e.kind in _CONVERSATION_KINDS]
    return matching[-n:]


__all__ = ["get_last_n_events"]
