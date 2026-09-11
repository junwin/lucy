from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping

from src.agent.caps import resolve_effective_cap
from src.config_manager import ConfigManager

DEFAULT_PROMPT_BUDGET_TOKENS = 12000
PROMPT_BUDGET_SAFETY_MARGIN = 500
CONTEXT_TEXT_SOFT_MAX_TOKENS = 2000


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class PromptBudget:
    history_budget: int
    system_tokens: int
    context_tokens: int
    document_tokens: int
    digest_tokens: int
    user_tokens: int


class TokenBudgetAllocator:
    """Own prompt token estimation and budget arithmetic."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def allocate_history_budget(
        self,
        *,
        agent: Any,
        system_text_parts: Iterable[str],
        context_text: str,
        document_text: str,
        digest_text: str,
        user_text: str,
    ) -> PromptBudget:
        system_tokens = estimate_tokens_from_text("\n\n".join(system_text_parts))
        context_tokens = estimate_tokens_from_text(context_text or "")
        document_tokens = estimate_tokens_from_text(document_text or "")
        digest_tokens = estimate_tokens_from_text(digest_text or "")
        user_tokens = estimate_tokens_from_text(user_text or "")

        ceiling = resolve_effective_cap(
            "prompt_budget_max_tokens",
            agent,
            self.config,
            DEFAULT_PROMPT_BUDGET_TOKENS,
        )
        history_budget = (
            ceiling
            - system_tokens
            - context_tokens
            - document_tokens
            - digest_tokens
            - user_tokens
            - PROMPT_BUDGET_SAFETY_MARGIN
        )

        logging.info(
            "PromptBuilder.history_budget: ceiling=%d system=%d context=%d obsidian=%d digest=%d user=%d safety_margin=%d -> history_budget=%d",
            ceiling,
            system_tokens,
            context_tokens,
            document_tokens,
            digest_tokens,
            user_tokens,
            PROMPT_BUDGET_SAFETY_MARGIN,
            history_budget,
        )
        return PromptBudget(
            history_budget=history_budget,
            system_tokens=system_tokens,
            context_tokens=context_tokens,
            document_tokens=document_tokens,
            digest_tokens=digest_tokens,
            user_tokens=user_tokens,
        )

    def apply_context_soft_max(
        self,
        *,
        context_text: str,
        agent: Any,
        account_name: str,
        context_name: str,
        agent_name: str,
    ) -> str:
        try:
            soft_max = resolve_effective_cap(
                "context_text_soft_max_tokens",
                agent,
                self.config,
                CONTEXT_TEXT_SOFT_MAX_TOKENS,
            )
            ctx_tokens = estimate_tokens_from_text(context_text or "")
            if ctx_tokens <= soft_max:
                return context_text

            logging.warning(
                "PromptBuilder: context text (%d tokens) exceeds soft max (%d tokens) — agent=%s account=%s context=%s; truncating",
                ctx_tokens,
                soft_max,
                agent_name,
                account_name,
                context_name or "(none)",
            )
            allowed_chars = max(0, soft_max * 4)
            truncated = (context_text or "")[:allowed_chars]
            truncated += "\n\n[Context truncated due to token budget]"
            logging.info(
                "PromptBuilder: truncated context_text to %d chars (soft_max=%d tokens) for account=%s context=%s",
                len(truncated),
                soft_max,
                account_name,
                context_name or "(none)",
            )
            return truncated
        except Exception:
            logging.exception("PromptBuilder: failed while enforcing context soft max")
            return context_text

    @staticmethod
    def build_breakdown(
        *,
        budget: PromptBudget,
        history_messages: Iterable[Mapping[str, Any]],
        overflow_digest_text: str,
    ) -> Dict[str, int]:
        history_tokens = sum(
            estimate_tokens_from_text(
                m["content"] if isinstance(m.get("content"), str) else str(m.get("content"))
            )
            for m in history_messages
        )
        overflow_tokens = estimate_tokens_from_text(overflow_digest_text)
        total_without_handlers = (
            budget.system_tokens
            + budget.context_tokens
            + budget.document_tokens
            + budget.digest_tokens
            + history_tokens
            + overflow_tokens
            + budget.user_tokens
        )
        return {
            "system_session": budget.system_tokens,
            "context_text": budget.context_tokens,
            "obsidian_notes": budget.document_tokens,
            "digest_embeddings": budget.digest_tokens,
            "chat_history": history_tokens,
            "overflow_digest": overflow_tokens,
            "current_user_message": budget.user_tokens,
            "total_without_handlers": total_without_handlers,
        }
