from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from injector import inject

from src.agent import Agent, AgentManager
from src.coala_memory.episodic import EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult
from src.config_manager import ConfigManager
from src.prompt_builders.attachment_resolver import AttachmentResolver
from src.prompt_builders.context_retrievers import (
    DEFAULT_SEARCH_NAMESPACES,
    DIGEST_SCORE_THRESHOLD,
    DIGEST_SEARCH_NAMESPACES,
    DOC_EMBEDDING_SCORE_THRESHOLD,
    DigestContextRetriever,
    SemanticContextRetriever,
)
from src.prompt_builders.history_selector import HistorySelector
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.prompt_builders.prompt_sections import PromptSections
from src.prompt_builders.token_budget import (
    CONTEXT_TEXT_SOFT_MAX_TOKENS,
    DEFAULT_PROMPT_BUDGET_TOKENS,
    PROMPT_BUDGET_SAFETY_MARGIN,
    TokenBudgetAllocator,
    estimate_tokens_from_text,
)
from src.storage.base import Storage
from src.storage.interfaces import EmbeddingStore

CONVERSATION_EVENT_KINDS = ["user_message", "assistant_message"]


class PromptBuilder(PromptBuilderInterface):
    """Thin prompt orchestrator over focused prompt-building collaborators."""

    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        embedding_facade=None,
        embedding_store: Optional[EmbeddingStore] = None,
        semantic_memory=None,
        episodic_memory: Optional[EpisodicMemory] = None,
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.embedding_facade = embedding_facade
        self.embedding_store = embedding_store
        self.semantic_memory = semantic_memory
        self.episodic_memory = episodic_memory
        self._last_prompt_token_breakdown: Dict[str, int] = {}

        self._token_budget = TokenBudgetAllocator(config)
        self._attachment_resolver = AttachmentResolver(config)
        self._semantic_context_retriever = SemanticContextRetriever(semantic_memory)
        self._digest_context_retriever = DigestContextRetriever(
            storage=storage,
            embedding_facade=embedding_facade,
            embedding_store=embedding_store,
        )
        self._history_selector = HistorySelector()
        self._sections = PromptSections()

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
    ) -> List[Dict[str, Any]]:
        """Build the full provider-neutral prompt message list."""
        logging.info("PromptBuilder.build_prompt: context_type=%s", context_type)

        agent: Optional[Agent] = self.agent_manager.get_agent(agent_name)
        use_embeddings = bool(agent and agent.use_embeddings)
        max_convs = agent.max_prompt_conversations if agent else 6

        if not context_name and agent is not None:
            resolved = getattr(agent, "default_context", None)
            if resolved:
                context_name = str(resolved).strip() or ""

        system_message = self._build_agent_system_message(agent_name, agent)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]
        system_text_parts: List[str] = [system_message]

        if conversation_id and conversation_id not in ("none", "new"):
            session_info_msg = f"Current session ID: {conversation_id}"
            messages.append({"role": "system", "content": session_info_msg})
            system_text_parts.append(session_info_msg)

        episodic_result = self._recall_current_episode(
            conversation_id=conversation_id,
            account_name=account_name,
            agent_name=agent_name,
            max_events=max_convs,
        )
        self._append_session_info(
            messages=messages,
            system_text_parts=system_text_parts,
            episodic_result=episodic_result,
            conversation_id=conversation_id,
            agent_name=agent_name,
        )

        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})
                system_text_parts.append(extra.strip())

        context_text = self._get_context_text(account_name=account_name, context_name=context_name)
        context_text = self._apply_context_soft_max(
            context_text=context_text,
            agent=agent,
            account_name=account_name,
            context_name=context_name,
            agent_name=agent_name,
        )
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Additional context for this conversation:\n{context_text}",
                }
            )

        context_data = self._get_context_data(account_name=account_name, context_name=context_name)
        doc_contexts = self._load_semantic_contexts(
            content_text=content_text,
            account_name=account_name,
            agent_name=agent_name,
            agent=agent,
            context_type=context_type,
            context_data=context_data,
            use_embeddings=use_embeddings,
        )
        obsidian_text = (
            "\n\n".join((ctx.get("snippet") or "") for ctx in doc_contexts)
            if doc_contexts
            else ""
        )

        digest_contexts = self._load_digest_contexts(
            content_text=content_text,
            account_name=account_name,
            agent_name=agent_name,
        )
        digest_text = (
            "\n\n".join((d.get("snippet") or "") for d in digest_contexts)
            if digest_contexts
            else ""
        )

        user_message = self._build_user_message(
            content_text=content_text,
            account_name=account_name,
            image_ids=image_ids,
            file_ids=file_ids,
            agent=agent,
            supports_images=supports_images,
        )

        try:
            budget = self._token_budget.allocate_history_budget(
                agent=agent,
                system_text_parts=system_text_parts,
                context_text=context_text,
                document_text=obsidian_text,
                digest_text=digest_text,
                user_text=content_text,
            )
            history_messages, overflow_digest_text = self._select_history(
                episodic_result=episodic_result,
                max_convs=max_convs,
                history_budget=budget.history_budget,
                messages=messages,
                account_name=account_name,
                conversation_id=conversation_id,
                agent_name=agent_name,
            )
            messages.extend(history_messages)

            self._last_prompt_token_breakdown = self._token_budget.build_breakdown(
                budget=budget,
                history_messages=history_messages,
                overflow_digest_text=overflow_digest_text,
            )
            self._append_document_contexts(messages, doc_contexts)
            self._append_digest_contexts(messages, digest_contexts)
            messages = self._ensure_current_query(messages, user_message["content"])

            logging.info(
                "PromptBuilder.build_prompt: agent=%s account=%s session_id=%s context_type=%s context_name=%s history_messages=%d docs_used=%d digest_docs_used=%d attachments=%d supports_images=%s use_embeddings=%s",
                agent_name,
                account_name,
                conversation_id,
                context_type,
                context_name,
                len(history_messages),
                len(doc_contexts),
                len(digest_contexts),
                len(image_ids or []) + len(file_ids or []),
                supports_images,
                use_embeddings,
            )
        except Exception as ex:
            logging.exception("PromptBuilder: failed to compute token breakdown: %s", ex)

        return messages

    def _append_session_info(self, **kwargs: Any) -> None:
        self._sections.append_session_info(**kwargs)

    def _apply_context_soft_max(
        self,
        *,
        context_text: str,
        agent: Optional[Agent],
        account_name: str,
        context_name: str,
        agent_name: str,
    ) -> str:
        return self._token_budget.apply_context_soft_max(
            context_text=context_text,
            agent=agent,
            account_name=account_name,
            context_name=context_name,
            agent_name=agent_name,
        )

    def _get_context_data(self, *, account_name: str, context_name: str) -> Dict[str, Any]:
        if not context_name or context_name == "none":
            return {}
        ctx = self._get_context_state(account_name=account_name, context_name=context_name)
        if ctx is None:
            return {}
        data: Dict[str, Any] = {}
        namespaces = getattr(ctx, "search_namespaces", None)
        if isinstance(namespaces, list):
            data["search_namespaces"] = namespaces
        extra = getattr(ctx, "extra", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                data.setdefault(key, value)
        return data

    def _load_semantic_contexts(
        self,
        *,
        content_text: str,
        account_name: str,
        agent_name: str,
        agent: Optional[Agent],
        context_type: str,
        context_data: Dict[str, Any],
        use_embeddings: bool,
    ) -> List[Dict[str, Any]]:
        if context_type not in ("documents", "hybrid"):
            return []
        if not use_embeddings:
            logging.info(
                "PromptBuilder: agent=%s has use_embeddings disabled; semantic document recall skipped",
                agent_name,
            )
            return []
        try:
            return self._get_semantic_memory_context(
                query=content_text,
                account_name=account_name,
                namespaces=context_data.get("search_namespaces") or DEFAULT_SEARCH_NAMESPACES,
                top_k=agent.max_prompt_documents if agent else 3,
                max_chars=9000,
            )
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load semantic document context for %s/%s: %s",
                account_name,
                agent_name,
                ex,
            )
            return []

    def _load_digest_contexts(
        self,
        *,
        content_text: str,
        account_name: str,
        agent_name: str,
    ) -> List[Dict[str, Any]]:
        try:
            return self._get_digest_context(
                query=content_text,
                account_name=account_name,
                top_k=3,
                max_chars=3000,
            )
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load digest context for %s/%s: %s",
                account_name,
                agent_name,
                ex,
            )
            return []

    def _build_user_message(
        self,
        *,
        content_text: str,
        account_name: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        agent: Optional[Agent],
        supports_images: bool,
    ) -> Dict[str, Any]:
        if not (image_ids or file_ids):
            return {"role": "user", "content": content_text}
        content_parts: List[Dict[str, Any]] = [{"type": "text", "text": content_text}]
        content_parts.extend(
            self._resolve_attachments(
                account_name=account_name,
                image_ids=image_ids,
                file_ids=file_ids,
                agent_allowed_tools=agent.allowed_tools if agent else None,
                supports_images=supports_images,
            )
        )
        return {"role": "user", "content": content_parts}

    def _select_history(
        self,
        *,
        episodic_result: Optional[EpisodicMemoryResult],
        max_convs: int,
        history_budget: int,
        messages: List[Dict[str, Any]],
        account_name: str,
        conversation_id: str,
        agent_name: str,
    ) -> tuple[List[Dict[str, str]], str]:
        return self._history_selector.select(
            episodic_result=episodic_result,
            max_convs=max_convs,
            history_budget=history_budget,
            messages=messages,
            account_name=account_name,
            conversation_id=conversation_id,
            agent_name=agent_name,
            summarize_overflow=self._summarize_overflow,
            save_overflow_digest=self._save_overflow_digest,
        )

    def _append_document_contexts(
        self, messages: List[Dict[str, Any]], doc_contexts: List[Dict[str, Any]]
    ) -> None:
        self._sections.append_document_contexts(messages, doc_contexts)

    def _append_digest_contexts(
        self, messages: List[Dict[str, Any]], digest_contexts: List[Dict[str, Any]]
    ) -> None:
        self._sections.append_digest_contexts(messages, digest_contexts)

    def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str:
        return self._sections.build_agent_system_message(agent_name, agent)

    def _recall_current_episode(
        self,
        *,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        max_events: int,
    ) -> Optional[EpisodicMemoryResult]:
        if self.episodic_memory is None:
            return None
        if not conversation_id or conversation_id in ("none", "new"):
            return None
        try:
            return self.episodic_memory.recall(
                EpisodicMemoryRequest(
                    account_name=account_name,
                    agent_name=agent_name,
                    conversation_id=conversation_id,
                    max_events=max_events,
                    event_kinds=list(CONVERSATION_EVENT_KINDS),
                    include_session_metadata=True,
                    include_recent_history=True,
                    include_archived_digests=False,
                )
            )
        except Exception as ex:
            logging.warning(
                "PromptBuilder: episodic recall failed for session %s account=%s agent=%s: %s; returning empty history",
                conversation_id,
                account_name,
                agent_name,
                ex,
            )
            return None

    @staticmethod
    def _event_content(event: Any) -> str:
        return HistorySelector.event_content(event)

    def _get_semantic_memory_context(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 9000,
        score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        return self._semantic_context_retriever.retrieve(
            query=query,
            account_name=account_name,
            namespaces=namespaces,
            top_k=top_k,
            max_chars=max_chars,
            score_threshold=score_threshold,
        )

    def _get_digest_context(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 3000,
    ) -> List[Dict[str, Any]]:
        return self._digest_context_retriever.retrieve(
            query=query,
            account_name=account_name,
            namespaces=namespaces,
            top_k=top_k,
            max_chars=max_chars,
        )

    def _resolve_attachments(
        self,
        *,
        account_name: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        agent_allowed_tools: Optional[List[str]] = None,
        supports_images: bool = True,
    ) -> List[Dict[str, Any]]:
        return self._attachment_resolver.resolve(
            account_name=account_name,
            image_ids=image_ids,
            file_ids=file_ids,
            agent_allowed_tools=agent_allowed_tools,
            supports_images=supports_images,
        )

    def _build_images_dir(self) -> str:
        return self._attachment_resolver.build_images_dir()

    def _build_digests_dir(self, account_name: str) -> Path:
        return Path("data") / "digests" / account_name

    def _save_overflow_digest(
        self,
        *,
        account_name: str,
        conversation_id: str,
        new_snippet: str,
    ) -> Optional[str]:
        digest_dir = self._build_digests_dir(account_name)
        digest_dir.mkdir(parents=True, exist_ok=True)
        output_path = digest_dir / f"{conversation_id}_overflow.md"

        existing = ""
        try:
            if output_path.exists():
                existing = output_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

        combined = existing + "\n\n" + new_snippet if existing else new_snippet
        try:
            output_path.write_text(combined, encoding="utf-8")
            logging.info(
                "PromptBuilder: saved overflow digest to %s (session=%s, chars=%d)",
                output_path,
                conversation_id,
                len(combined),
            )
            return combined
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to write overflow digest for %s: %s",
                conversation_id,
                ex,
            )
            return None

    def _find_image_file(self, images_dir: str, account_name: str, img_id: str) -> Optional[str]:
        return self._attachment_resolver.find_image_file(images_dir, account_name, img_id)

    def _find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str]:
        return self._attachment_resolver.find_file(images_dir, account_name, file_id)

    @staticmethod
    def _guess_mime_from_path(path: str) -> str:
        return AttachmentResolver.guess_mime_from_path(path)

    def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]:
        """Memory seam overridden by CoALAPromptBuilder."""
        return None

    def _get_context_text(self, account_name: str, context_name: str) -> str:
        return self._sections.context_text(self._get_context_state(account_name, context_name))

    def _ensure_current_query(
        self, messages: List[Dict[str, Any]], current_query: Any
    ) -> List[Dict[str, Any]]:
        return self._sections.ensure_current_query(messages, current_query)

    def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str:
        return self._history_selector.summarize_overflow(texts, max_chars=max_chars)


__all__ = [
    "PromptBuilder",
    "estimate_tokens_from_text",
    "DEFAULT_PROMPT_BUDGET_TOKENS",
    "PROMPT_BUDGET_SAFETY_MARGIN",
    "CONTEXT_TEXT_SOFT_MAX_TOKENS",
    "DIGEST_SCORE_THRESHOLD",
    "DIGEST_SEARCH_NAMESPACES",
    "DOC_EMBEDDING_SCORE_THRESHOLD",
    "DEFAULT_SEARCH_NAMESPACES",
    "CONVERSATION_EVENT_KINDS",
]
