# src/prompt_builders/prompt_builder.py

import logging
from typing import Any, Dict, List, Optional
from injector import inject

from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.storage.base import Storage
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.utils.document_context import get_document_context

DEFAULT_PROMPT_BUDGET_TOKENS = 12000

DEFAULT_SOURCE_BUDGETS = {
    "agent": 0.4,
    "account": 0.4,
    "context": 0.2,
}


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def get_prompt_budget_for_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    prompt_budget_tokens = int(agent.get("prompt_budget_tokens", DEFAULT_PROMPT_BUDGET_TOKENS))

    source_fracs = agent.get("source_budgets", {}) or {}
    merged_fracs = {**DEFAULT_SOURCE_BUDGETS, **source_fracs}

    total_frac = sum(merged_fracs.values()) or 1.0
    normalized_fracs = {k: v / total_frac for k, v in merged_fracs.items()}

    source_budgets = {name: int(prompt_budget_tokens * frac) for name, frac in normalized_fracs.items()}

    return {"prompt_budget_tokens": prompt_budget_tokens, "source_budgets": source_budgets}


class PromptBuilder(PromptBuilderInterface):
    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage

    def build_prompt(
        self,
        *,
        content_text: str,
        conversation_id: str,
        agent_name: str,
        account_name: str,
        context_type: str = "none",
        max_prompt_chars: int = 6000,
        max_prompt_conversations: int = 20,
        context_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Build the full prompt (list of messages) for a model call.

        Logging and error handling goals:
        - Log how many history messages and document snippets are included.
        - Log when no chat session is found for the given conversation_id.
        - Fail soft on context/document errors (warn and continue).
        """
        logging.info("PromptBuilder.build_prompt: context_type=%s", context_type)

        agent = self.agent_manager.get_agent(agent_name)
        _budget_info = get_prompt_budget_for_agent(agent)
        # source_budgets = _budget_info["source_budgets"]  # reserved for future use

        system_message = self._build_agent_system_message(agent_name, agent)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_message}]

        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})

        # --- Chat history ---
        history_messages = self._get_chat_history_messages(
            conversation_id=conversation_id,
            account_name=account_name,
            agent_name=agent_name,
            max_conversations=max_prompt_conversations,
        )
        messages.extend(history_messages)

        # --- Named context (from storage) ---
        context_text = self._get_context_text(account_name=account_name, context_name=context_name)
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Additional context for this conversation:\n{context_text}",
                }
            )

        # --- External documents ---
        doc_contexts: List[Dict[str, Any]] = []
        if context_type in ("documents", "hybrid"):
            try:
                doc_contexts = get_document_context(
                    storage=self.storage,
                    account_name=account_name,
                    query=content_text,
                    kind="obsidian_note",
                    limit=3,
                    max_chars=2000,
                )
                if doc_contexts:
                    doc_lines: List[str] = [
                        "The following Obsidian notes may be relevant to the user's question:",
                    ]
                    for idx, ctx in enumerate(doc_contexts, start=1):
                        title = ctx.get("title") or "(untitled)"
                        tags = ctx.get("tags") or []
                        snippet = ctx.get("snippet") or ""
                        truncated = ctx.get("truncated") or False
                        tag_str = ", ".join(tags)
                        header = f"{idx}. Title: {title}"
                        if tag_str:
                            header += f" | Tags: {tag_str}"
                        doc_lines.append(header)
                        doc_lines.append(snippet)
                        if truncated:
                            doc_lines.append("[Note: content truncated]")
                        doc_lines.append("")

                    messages.append({"role": "system", "content": "\n".join(doc_lines).strip()})
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to load document context for %s/%s: %s",
                    account_name,
                    agent_name,
                    ex,
                )

        # --- Current user message ---
        messages.append({"role": "user", "content": content_text})
        messages = self._ensure_current_query(messages, content_text)
        # messages = self._cap_prompt_by_chars_preserving_last_user(messages, max_prompt_chars)

        # --- Summary logging ---
        logging.info(
            "PromptBuilder.build_prompt: agent=%s account=%s session_id=%s "
            "context_type=%s context_name=%s history_messages=%d docs_used=%d",
            agent_name,
            account_name,
            conversation_id,
            context_type,
            context_name,
            len(history_messages),
            len(doc_contexts),
        )

        return messages

    # --- helper methods ---

    def _build_agent_system_message(self, agent_name: str, agent: Dict[str, Any]) -> str:
        parts: List[str] = []
        parts.append(agent.get("system_prompt", f"You are {agent_name}, a helpful assistant."))
        if agent.get("persona"):
            parts.append(agent["persona"])
        if agent.get("style_prompt"):
            parts.append(agent["style_prompt"])
        return "\n\n".join(parts)

    def _get_chat_history_messages(
        self,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        max_conversations: int,
        max_messages_per_session: int = 50,
    ) -> List[Dict[str, str]]:
        if not conversation_id or conversation_id in ("none", "new"):
            return []
        if max_conversations <= 0:
            return []

        try:
            session = self.storage.get_chat_session(conversation_id)
        except Exception as ex:
            logging.warning(
                "PromptBuilder: error loading chat session %s for account=%s agent=%s: %s",
                conversation_id,
                account_name,
                agent_name,
                ex,
            )
            return []

        if not session:
            logging.warning(
                "PromptBuilder: no chat session found for session_id=%s account=%s agent=%s; "
                "building prompt without history",
                conversation_id,
                account_name,
                agent_name,
            )
            return []

        msgs = session.messages[-max_messages_per_session:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    def _get_context_text(self, account_name: str, context_name: str) -> str:
        """Load context text from storage.

        For now this is a simple, read-only lookup that expects a ContextState
        whose data dict may contain a "text" field with free-form content.
        """
        if not context_name or context_name == "none":
            return ""

        try:
            ctx = self.storage.get_context(account_name, context_name)
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load context %s for %s: %s",
                context_name,
                account_name,
                ex,
            )
            return ""

        if ctx is None:
            logging.warning(
                "PromptBuilder: context %s not found for account=%s",
                context_name,
                account_name,
            )
            return ""

        data = getattr(ctx, "data", None)
        if isinstance(data, dict):
            text = data.get("text")
            if isinstance(text, str):
                return text

        return ""

    def _ensure_current_query(self, messages: List[Dict[str, str]], current_query: str) -> List[Dict[str, str]]:
        if not messages:
            return [{"role": "user", "content": current_query}]
        last = messages[-1]
        if last.get("role") == "user" and (last.get("content") or "") == current_query:
            return messages
        return messages + [{"role": "user", "content": current_query}]
