# Replacement for src/prompt_builders/prompt_builder.py
# Adds support for extra_system_messages (list[str]) and ensures the current user query isn't dropped.

import logging
from typing import Any, Dict, List, Optional

from src.container_config import container
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.context.context_manager import ContextManager
from src.storage.base import Storage
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface

DEFAULT_PROMPT_BUDGET_TOKENS = 12000

DEFAULT_SOURCE_BUDGETS = {
    "agent": 0.4,      # system / persona
    "account": 0.4,    # chat history
    "context": 0.2,    # explicit context_text
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
    def __init__(self):
        self.agent_manager: AgentManager = container.get(AgentManager)
        self.config: ConfigManager = container.get(ConfigManager)
        self.storage: Storage = container.get(Storage)
        self.context_manager = ContextManager(self.config)

    def build_prompt(
        self,
        content_text: str,
        conversationId: str,
        agent_name: str,
        account_name: str,
        context_type: str = "none",
        max_prompt_chars: int = 6000,
        max_prompt_conversations: int = 20,
        context_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        logging.info("PromptBuilder.build_prompt: context_type=%s", context_type)

        agent = self.agent_manager.get_agent(agent_name)
        budget_info = get_prompt_budget_for_agent(agent)
        source_budgets = budget_info["source_budgets"]

        # 1) primary system prompt
        system_message = self._build_agent_system_message(agent_name, agent)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_message}]

        # 1b) extra system messages (e.g., SME guidance)
        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})

        # 2) history
        history_messages = self._get_chat_history_messages(
            conversationId=conversationId,
            account_name=account_name,
            agent_name=agent_name,
            max_conversations=max_prompt_conversations,
        )
        messages.extend(history_messages)

        # 3) context
        context_text = self._get_context_text(account_name=account_name, context_name=context_name)
        if context_text:
            messages.append({"role": "system", "content": f"Additional context for this conversation:\n{context_text}"})

        # 4) user query last
        messages.append({"role": "user", "content": content_text})

        # Ensure the current query isn't dropped by other caps
        messages = self._ensure_current_query(messages, content_text)

        # Hard cap chars, but never remove the final user query
        # messages = self._cap_prompt_by_chars_preserving_last_user(messages, max_prompt_chars)

        return messages

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
        conversationId: str,
        account_name: str,
        agent_name: str,
        max_conversations: int,
        max_messages_per_session: int = 50,
    ) -> List[Dict[str, str]]:
        if not conversationId or conversationId in ("none", "new"):
            return []

        session = self.storage.get_chat_session(conversationId)
        if not session:
            return []

        msgs = session.messages[-max_messages_per_session:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    def _get_context_text(self, account_name: str, context_name: str) -> str:
        if not context_name or context_name == "none":
            return ""
        try:
            ctx = self.context_manager.get_context(account_name, context_name)
        except Exception as ex:
            logging.warning("PromptBuilder: failed to load context %s for %s: %s", context_name, account_name, ex)
            return ""
        if ctx is None:
            return ""
        return ctx.context_formated_text2("compact")

    def _ensure_current_query(self, messages: List[Dict[str, str]], current_query: str) -> List[Dict[str, str]]:
        if not messages:
            return [{"role": "user", "content": current_query}]
        last = messages[-1]
        if last.get("role") == "user" and (last.get("content") or "") == current_query:
            return messages
        return messages + [{"role": "user", "content": current_query}]

    def _cap_prompt_by_chars_preserving_last_user(self, messages: List[Dict[str, str]], max_chars: int) -> List[Dict[str, str]]:
        if max_chars <= 0 or not messages:
            return messages

        last_msg = messages[-1]
        prefix = messages[:-1]

        total = 0
        capped_prefix: List[Dict[str, str]] = []
        for msg in prefix:
            content = msg.get("content", "")
            length = len(content)
            if total + length <= max_chars:
                capped_prefix.append(msg)
                total += length
            else:
                remaining = max_chars - total
                if remaining > 0:
                    capped_prefix.append({"role": msg["role"], "content": content[:remaining]})
                    total += remaining
                break

        remaining_for_last = max_chars - total
        last_content = last_msg.get("content", "") or ""
        if remaining_for_last <= 0:
            return [{"role": last_msg["role"], "content": last_content[:max_chars]}]

        capped_last = {"role": last_msg["role"], "content": last_content[:remaining_for_last]}
        return capped_prefix + [capped_last]