from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional

from galet_prompt_builder import (
    PromptCompiler,
    PromptPolicy,
    PromptRequest,
)
from galet_memory import EpisodicMemory, ProceduralMemory, ProceduralMemoryRequest

from src.agent import Agent, AgentManager
from src.coala_memory.semantic import (
    SemanticMemory,
    SemanticMemoryRequest,
)
from src.config_manager import ConfigManager
from src.prompt_builders.attachment_resolver import AttachmentResolver
from src.prompt_builders.constants import DEFAULT_SEARCH_NAMESPACES
from src.prompt_builders.prompt_builder_interface import (
    ChatMessageDict,
    PromptBuilderInterface,
)
from src.prompt_builders.prompt_sections import PromptSections
from src.storage.base import Storage


CONVERSATION_EVENT_KINDS = (
    "user_message",
    "assistant_message",
    "session_digest",
)


@dataclass(frozen=True)
class GaletPromptPolicy(PromptPolicy):
    """Lucy config and agent overrides for the Galet prompt policy."""

    procedural_tokens: int = 1500

    @classmethod
    def from_config(
        cls,
        config: ConfigManager,
        agent: Optional[Agent],
    ) -> "GaletPromptPolicy":
        configured = config.get("galet_prompt_builder", {}) or {}
        if not isinstance(configured, dict):
            raise ValueError("galet_prompt_builder must be an object")

        defaults = cls()
        values = {item.name: configured.get(item.name, getattr(defaults, item.name))
                  for item in fields(cls)}
        if agent is not None:
            if agent.prompt_budget_max_tokens is not None:
                values["total_tokens"] = agent.prompt_budget_max_tokens
            values["maximum_events"] = agent.max_prompt_conversations
            values["maximum_semantic_documents"] = agent.max_prompt_documents
        return cls(**values)


class _LucySemanticMemoryAdapter:
    def __init__(self, memory: SemanticMemory) -> None:
        self.memory = memory

    def recall(self, request: Any) -> Any:
        return self.memory.recall(
            SemanticMemoryRequest(
                account_name=request.account_name,
                query=request.query,
                use_embeddings=True,
                namespaces=list(request.namespaces),
                top_k=request.top_k,
                max_chars=request.max_chars,
                score_threshold=request.score_threshold,
            )
        )


class GaletPromptBuilderAdapter(PromptBuilderInterface):
    """Adapt Lucy's prompt contract to the standalone Galet compiler.

    Lucy remains responsible for agent configuration, attachment resolution,
    and choosing policy. Galet owns memory selection, budgets, and rendering.
    """

    def __init__(
        self,
        *,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        semantic_memory: SemanticMemory,
        episodic_memory: EpisodicMemory,
        procedural_memory: ProceduralMemory,
        compiler_class: type[PromptCompiler] = PromptCompiler,
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.semantic_memory = semantic_memory
        self.episodic_memory = episodic_memory
        self.procedural_memory = procedural_memory
        self.compiler_class = compiler_class
        self._attachments = AttachmentResolver(config)
        self._last_prompt_token_breakdown: Dict[str, int] = {}
        self._last_compiled_prompt: Any = None

    def build_prompt(
        self,
        *,
        content_text: str,
        conversation_id: str,
        agent_name: str,
        account_name: str,
        context_type: str = "none",
        max_prompt_chars: int = 6000,
        context_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
        supports_images: bool = True,
    ) -> List[ChatMessageDict]:
        del max_prompt_chars  # Legacy character cap; Galet uses token budgets.
        agent = self.agent_manager.get_agent(agent_name)
        if not context_name and agent is not None and agent.default_context:
            context_name = str(agent.default_context).strip()

        policy = GaletPromptPolicy.from_config(self.config, agent)
        namespaces = self._semantic_namespaces(account_name, context_name)
        include_semantic = bool(
            agent
            and agent.use_embeddings
            and context_type in ("documents", "hybrid")
            and namespaces
        )

        system_instructions = [
            PromptSections.build_agent_system_message(agent_name, agent)
        ]
        if conversation_id and conversation_id not in ("none", "new"):
            system_instructions.append(f"Current session ID: {conversation_id}")
        system_instructions.extend(
            value.strip()
            for value in (extra_system_messages or [])
            if value and value.strip()
        )

        compiler = self.compiler_class(
            procedural_memory=self.procedural_memory,
            episodic_memory=self.episodic_memory,
            semantic_memory=_LucySemanticMemoryAdapter(self.semantic_memory),
        )
        compiled = compiler.build(
            PromptRequest(
                account_name=account_name,
                current_input=content_text,
                system_instructions=tuple(system_instructions),
                conversation_id=(
                    conversation_id
                    if conversation_id not in ("none", "new")
                    else ""
                ),
                context_name=(
                    context_name if context_name != "none" else ""
                ),
                semantic_namespaces=tuple(namespaces),
                episodic_event_kinds=CONVERSATION_EVENT_KINDS,
                include_structured_episodic_events=False,
                include_procedural=bool(context_name),
                include_episodic=True,
                include_semantic=include_semantic,
                include_digests=True,
            ),
            policy,
        )
        self._last_compiled_prompt = compiled
        self._last_prompt_token_breakdown = self._metrics_breakdown(
            compiled.metrics
        )
        messages: List[ChatMessageDict] = list(compiled.provider_messages)
        self._replace_current_input_with_attachments(
            messages,
            content_text=content_text,
            account_name=account_name,
            agent=agent,
            image_ids=image_ids,
            file_ids=file_ids,
            supports_images=supports_images,
        )
        return messages

    def _semantic_namespaces(
        self, account_name: str, context_name: str
    ) -> List[str]:
        if not context_name or context_name == "none":
            return list(DEFAULT_SEARCH_NAMESPACES)
        result = self.procedural_memory.recall(
            ProceduralMemoryRequest(
                account_name=account_name,
                context_name=context_name,
                create_if_missing=False,
                include_resolved_text=False,
                include_skills=False,
                include_required_tools=False,
            )
        )
        return list(result.search_namespaces or DEFAULT_SEARCH_NAMESPACES)

    def _replace_current_input_with_attachments(
        self,
        messages: List[ChatMessageDict],
        *,
        content_text: str,
        account_name: str,
        agent: Optional[Agent],
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        supports_images: bool,
    ) -> None:
        if not (image_ids or file_ids):
            return
        reference_text = self._attachments.reference_text(image_ids, file_ids)
        prompt_text = "\n\n".join(filter(None, [content_text, reference_text]))
        content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt_text}
        ]
        content.extend(
            self._attachments.resolve(
                account_name=account_name,
                image_ids=image_ids,
                file_ids=file_ids,
                agent_allowed_tools=(agent.allowed_tools if agent else None),
                supports_images=supports_images,
            )
        )
        messages[-1] = {"role": "user", "content": content}

    @staticmethod
    def _metrics_breakdown(metrics: Any) -> Dict[str, int]:
        return {
            "system_session": metrics.system.used_tokens,
            "context_text": metrics.procedural.used_tokens,
            "obsidian_notes": metrics.semantic.used_tokens,
            "digest_embeddings": metrics.episodic_digests.used_tokens,
            "chat_history": metrics.episodic_events.used_tokens,
            "current_user_message": metrics.current_input.used_tokens,
            "total_without_handlers": metrics.total_used_tokens,
        }


__all__ = ["GaletPromptBuilderAdapter", "GaletPromptPolicy"]
