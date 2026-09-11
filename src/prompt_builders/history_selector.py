from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.coala_memory.episodic import EpisodicMemoryResult
from src.prompt_builders.token_budget import estimate_tokens_from_text


class HistorySelector:
    """Select recent conversational events within the prompt history budget."""

    @staticmethod
    def event_content(event: Any) -> str:
        value = getattr(event, "content", None)
        return value if isinstance(value, str) else str(value)

    def select(
        self,
        *,
        episodic_result: Optional[EpisodicMemoryResult],
        max_convs: int,
        history_budget: int,
        messages: List[Dict[str, Any]],
        account_name: str,
        conversation_id: str,
        agent_name: str,
        summarize_overflow: Callable[[List[str]], str],
        save_overflow_digest: Callable[..., Optional[str]],
    ) -> Tuple[List[Dict[str, str]], str]:
        matching = list(episodic_result.events) if episodic_result is not None else []
        original_match_count = (
            len(matching) + episodic_result.dropped_event_count
            if episodic_result is not None
            else 0
        )
        matching = [] if max_convs <= 0 else matching[-max_convs:]

        if max_convs <= 0:
            logging.info(
                "PromptBuilder.history: max_prompt_conversations=%d — skipping all chat history for agent=%s",
                max_convs,
                agent_name,
            )
        elif len(matching) < original_match_count:
            logging.info(
                "PromptBuilder.history: max_prompt_conversations=%d capped %d events down to %d for agent=%s",
                max_convs,
                original_match_count,
                len(matching),
                agent_name,
            )

        remaining = history_budget
        included: List[Any] = []
        for event in reversed(matching):
            payload = self.event_content(event)
            tok = estimate_tokens_from_text(payload)
            if remaining >= tok:
                included.insert(0, event)
                remaining -= tok
            else:
                if not included:
                    included.insert(0, event)
                break

        included_set = {id(item) for item in included}
        dropped = [event for event in matching if id(event) not in included_set]
        overflow_digest_text = ""

        if dropped:
            try:
                digest_snippet = summarize_overflow(
                    [self.event_content(event) for event in dropped]
                )
                saved_digest = save_overflow_digest(
                    account_name=account_name,
                    conversation_id=conversation_id,
                    new_snippet=digest_snippet,
                )
                overflow_digest_text = saved_digest or digest_snippet
                messages.append(
                    {
                        "role": "system",
                        "content": f"Earlier in this session:\n{overflow_digest_text}",
                    }
                )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to persist session digest for %s: %s",
                    conversation_id,
                    ex,
                )

        history_messages = [
            {"role": event.role, "content": self.event_content(event)}
            for event in included
        ]
        return history_messages, overflow_digest_text

    @staticmethod
    def summarize_overflow(texts: List[str], max_chars: int = 800) -> str:
        if not texts:
            return ""
        header = f"{len(texts)} earlier messages were summarized."
        out_parts = [header]
        remaining = max_chars - len(header) - 2
        for text in texts:
            if remaining <= 0:
                break
            snippet = text.strip().replace("\n", " ")
            if not snippet:
                continue
            take = min(len(snippet), remaining)
            out_parts.append(snippet[:take])
            remaining -= take + 2
        combined = "\n\n".join(out_parts)
        return combined if len(combined) <= max_chars else combined[: max_chars - 3] + "..."
