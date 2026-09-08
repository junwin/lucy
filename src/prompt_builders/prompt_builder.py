# src/prompt_builders/prompt_builder.py

import base64
import glob
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from injector import inject

from src.agent import Agent, AgentManager
from src.agent.caps import resolve_effective_cap
from src.coala_memory.episodic import EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult
from src.coala_memory.semantic import SemanticMemory, SemanticMemoryRequest
from src.config_manager import ConfigManager
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.storage.base import Storage
from src.storage.interfaces import EmbeddingStore
from src.utils.text_snippet_loader import load_text_snippet

DEFAULT_PROMPT_BUDGET_TOKENS = 12000
PROMPT_BUDGET_SAFETY_MARGIN = 500

DIGEST_SCORE_THRESHOLD = 0.25
DIGEST_SEARCH_NAMESPACES = ["digests"]
DOC_EMBEDDING_SCORE_THRESHOLD = 0.25
CONTEXT_TEXT_SOFT_MAX_TOKENS = 2000
DEFAULT_SEARCH_NAMESPACES = ["external"]
CONVERSATION_EVENT_KINDS = ["user_message", "assistant_message"]


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


class PromptBuilder(PromptBuilderInterface):
    """Compose model prompts from agent configuration and CoALA memory results.

    PromptBuilder owns composition, token budgeting, attachment handling and
    overflow summarization. It does not read Chat2 or ContextStore directly;
    episodic, semantic and procedural retrieval live behind CoALA interfaces.
    """

    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        embedding_facade=None,  # retained for archived-digest retrieval
        embedding_store: Optional[EmbeddingStore] = None,
        semantic_memory: Optional[SemanticMemory] = None,
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

        context_text = self._get_context_text(
            account_name=account_name,
            context_name=context_name,
        )
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

        context_data = self._get_context_data(
            account_name=account_name,
            context_name=context_name,
        )

        doc_contexts = self._load_semantic_contexts(
            content_text=content_text,
            account_name=account_name,
            agent_name=agent_name,
            agent=agent,
            context_type=context_type,
            context_data=context_data,
            use_embeddings=use_embeddings,
        )
        obsidian_text = "\n\n".join(
            (ctx.get("snippet") or "") for ctx in doc_contexts
        ) if doc_contexts else ""

        digest_contexts = self._load_digest_contexts(
            content_text=content_text,
            account_name=account_name,
            agent_name=agent_name,
        )
        digest_text = "\n\n".join(
            (d.get("snippet") or "") for d in digest_contexts
        ) if digest_contexts else ""

        user_message = self._build_user_message(
            content_text=content_text,
            account_name=account_name,
            image_ids=image_ids,
            file_ids=file_ids,
            agent=agent,
            supports_images=supports_images,
        )

        try:
            system_tokens = estimate_tokens_from_text("\n\n".join(system_text_parts))
            context_tokens = estimate_tokens_from_text(context_text or "")
            obsidian_tokens = estimate_tokens_from_text(obsidian_text or "")
            digest_tokens = estimate_tokens_from_text(digest_text or "")
            user_tokens = estimate_tokens_from_text(content_text or "")

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
                - obsidian_tokens
                - digest_tokens
                - user_tokens
                - PROMPT_BUDGET_SAFETY_MARGIN
            )

            logging.info(
                "PromptBuilder.history_budget: ceiling=%d system=%d context=%d obsidian=%d digest=%d user=%d safety_margin=%d -> history_budget=%d",
                ceiling,
                system_tokens,
                context_tokens,
                obsidian_tokens,
                digest_tokens,
                user_tokens,
                PROMPT_BUDGET_SAFETY_MARGIN,
                history_budget,
            )

            history_messages, overflow_digest_text = self._select_history(
                episodic_result=episodic_result,
                max_convs=max_convs,
                history_budget=history_budget,
                messages=messages,
                account_name=account_name,
                conversation_id=conversation_id,
                agent_name=agent_name,
            )
            messages.extend(history_messages)

            history_tokens = sum(
                estimate_tokens_from_text(
                    m["content"] if isinstance(m.get("content"), str) else str(m.get("content"))
                )
                for m in history_messages
            )
            overflow_tokens = estimate_tokens_from_text(overflow_digest_text)
            total_without_handlers = (
                system_tokens
                + context_tokens
                + obsidian_tokens
                + digest_tokens
                + history_tokens
                + overflow_tokens
                + user_tokens
            )

            self._last_prompt_token_breakdown = {
                "system_session": system_tokens,
                "context_text": context_tokens,
                "obsidian_notes": obsidian_tokens,
                "digest_embeddings": digest_tokens,
                "chat_history": history_tokens,
                "overflow_digest": overflow_tokens,
                "current_user_message": user_tokens,
                "total_without_handlers": total_without_handlers,
            }

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

    def _append_session_info(
        self,
        *,
        messages: List[Dict[str, Any]],
        system_text_parts: List[str],
        episodic_result: Optional[EpisodicMemoryResult],
        conversation_id: str,
        agent_name: str,
    ) -> None:
        if conversation_id in ("none", "new", "") or episodic_result is None:
            return
        if not episodic_result.session_id or episodic_result.session_updated_at is None:
            return

        try:
            updated_at = episodic_result.session_updated_at
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            secs = (now - updated_at).total_seconds()
            if secs < 60:
                elapsed = f"{int(secs)}s ago"
            elif secs < 3600:
                elapsed = f"{int(secs / 60)}m ago"
            elif secs < 86400:
                elapsed = f"{int(secs / 3600)}h ago"
            else:
                elapsed = f"{int(secs / 86400)}d ago"

            info = f"Session: agent={episodic_result.session_agent_name or agent_name}"
            ctx_name = (
                episodic_result.session_context_name
                or episodic_result.session_friendly_name
            )
            if ctx_name:
                info += f", context={ctx_name}"
            info += f", last activity {elapsed} (timestamp: {updated_at.isoformat()}Z)"
            messages.append({"role": "system", "content": info})
            system_text_parts.append(info)
        except Exception:
            return

    def _apply_context_soft_max(
        self,
        *,
        context_text: str,
        agent: Optional[Agent],
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
            payload = self._event_content(event)
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
                digest_snippet = self._summarize_overflow(
                    [self._event_content(event) for event in dropped]
                )
                saved_digest = self._save_overflow_digest(
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
            {"role": event.role, "content": self._event_content(event)}
            for event in included
        ]
        return history_messages, overflow_digest_text

    def _append_document_contexts(
        self,
        messages: List[Dict[str, Any]],
        doc_contexts: List[Dict[str, Any]],
    ) -> None:
        if not doc_contexts:
            return
        lines = ["The following Obsidian notes may be relevant to the user's question:"]
        for idx, ctx in enumerate(doc_contexts, start=1):
            header = f"{idx}. Title: {ctx.get('title') or '(untitled)'}"
            tags = ctx.get("tags") or []
            if tags:
                header += f" | Tags: {', '.join(tags)}"
            lines.append(header)
            lines.append(ctx.get("snippet") or "")
            if ctx.get("truncated"):
                lines.append("[Note: content truncated]")
            lines.append("")
        messages.append({"role": "system", "content": "\n".join(lines).strip()})

    def _append_digest_contexts(
        self,
        messages: List[Dict[str, Any]],
        digest_contexts: List[Dict[str, Any]],
    ) -> None:
        if not digest_contexts:
            return
        lines = ["The following archived chat session digests may be relevant:"]
        for idx, dctx in enumerate(digest_contexts, start=1):
            lines.append(
                f"{idx}. Session {dctx.get('session_id') or 'unknown'} "
                f"(score: {dctx.get('score', 0):.3f})"
            )
            lines.append(dctx.get("snippet") or "")
            if dctx.get("truncated"):
                lines.append("[Digest truncated]")
            lines.append("")
        messages.append({"role": "system", "content": "\n".join(lines).strip()})

    def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str:
        if agent is None:
            return f"You are {agent_name}, a helpful assistant."

        parts: List[str] = [
            agent.system_prompt or f"You are {agent_name}, a helpful assistant."
        ]
        if agent.persona:
            parts.append(agent.persona)
        if agent.style_prompt:
            parts.append(agent.style_prompt)
        return "\n\n".join(parts)

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
        value = getattr(event, "content", None)
        return value if isinstance(value, str) else str(value)

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
        if not query or not query.strip() or self.semantic_memory is None:
            return []

        namespaces = list(namespaces or DEFAULT_SEARCH_NAMESPACES)
        result = self.semantic_memory.recall(
            SemanticMemoryRequest(
                account_name=account_name,
                query=query,
                use_embeddings=True,
                namespaces=namespaces,
                top_k=top_k,
                max_chars=max_chars,
                score_threshold=score_threshold,
                embedding_model="text-embedding-3-small",
            )
        )

        contexts = [
            {
                "title": doc.title,
                "tags": list(doc.tags),
                "snippet": doc.snippet,
                "truncated": doc.truncated,
                "score": doc.score,
                "source_id": doc.source_id,
            }
            for doc in result.documents
        ]
        logging.info(
            "PromptBuilder._get_semantic_memory_context: namespaces=%s selected=%d backend=%s",
            namespaces,
            len(contexts),
            result.metadata.get("backend", "unknown"),
        )
        return contexts

    def _get_digest_context(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 3000,
    ) -> List[Dict[str, Any]]:
        if self.embedding_facade is None or not query or not query.strip():
            return []

        try:
            response = self.embedding_facade.embed(
                [query], model="text-embedding-3-small"
            )
            embedding_store = self.embedding_store or self.storage
            results = embedding_store.query_embeddings(
                namespaces=namespaces or DIGEST_SEARCH_NAMESPACES,
                account_name=account_name,
                query_vector=response.embeddings[0],
                top_k=top_k,
            )

            logging.info(
                "PromptBuilder._get_digest_context: query='%s' top_k=%d raw=[%s]",
                query[:120].replace("\n", " "),
                top_k,
                ", ".join(f"{r.source_id}={score:.3f}" for r, score in results),
            )

            contexts: List[Dict[str, Any]] = []
            for record, score in results:
                if score < DIGEST_SCORE_THRESHOLD:
                    continue
                path = record.source_metadata.get("path") if record.source_metadata else None
                if not path:
                    continue
                snippet, truncated = load_text_snippet(path, max_chars=max_chars)
                if not snippet.strip():
                    continue
                contexts.append(
                    {
                        "session_id": record.source_id,
                        "snippet": snippet,
                        "truncated": truncated,
                        "score": score,
                    }
                )
            return contexts
        except Exception as ex:
            logging.warning(
                "PromptBuilder._get_digest_context: failed for account=%s: %s",
                account_name,
                ex,
            )
            return []

    def _resolve_attachments(
        self,
        *,
        account_name: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        agent_allowed_tools: Optional[List[str]] = None,
        supports_images: bool = True,
    ) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        images_dir = self._build_images_dir()
        any_image_marked = False

        for img_id in (image_ids or []):
            try:
                img_path = self._find_image_file(images_dir, account_name, img_id)
                if img_path is None:
                    logging.warning(
                        "PromptBuilder: image_id=%s not found for account=%s; skipping",
                        img_id,
                        account_name,
                    )
                    continue

                if not supports_images:
                    parts.append(
                        {
                            "type": "text",
                            "text": f"[Attached image: {img_id} — {os.path.basename(img_path)}]",
                        }
                    )
                    any_image_marked = True
                else:
                    with open(img_path, "rb") as file_handle:
                        raw = file_handle.read()
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "data": base64.b64encode(raw).decode("ascii"),
                                "mime_type": self._guess_mime_from_path(img_path),
                            },
                        }
                    )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to resolve image_id=%s for account=%s: %s",
                    img_id,
                    account_name,
                    ex,
                )

        if any_image_marked:
            parts.append(
                {
                    "type": "text",
                    "text": (
                        "Your model cannot see images. To analyze images: create a tasklist via "
                        "tasklists_manage (action='put') with a task that includes the image UUIDs "
                        "above in meta.image_ids as a list of strings. Then run it with "
                        "tasklists_run (worker_agent='colin'). Use the worker's output to answer the user."
                    ),
                }
            )

        for file_id in (file_ids or []):
            try:
                file_path = self._find_file(images_dir, account_name, file_id)
                if file_path is None:
                    logging.warning(
                        "PromptBuilder: file_id=%s not found for account=%s; skipping",
                        file_id,
                        account_name,
                    )
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as file_handle:
                        text = file_handle.read()
                except UnicodeDecodeError:
                    text = f"[Binary file: {os.path.basename(file_path)}]"
                parts.append(
                    {
                        "type": "text",
                        "text": f"[File: {os.path.basename(file_path)}]\n{text}",
                    }
                )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to resolve file_id=%s for account=%s: %s",
                    file_id,
                    account_name,
                    ex,
                )

        return parts

    def _build_images_dir(self) -> str:
        return os.path.join(
            self.config.get("storage_root_path", "/home/junwin/lucy_storage"),
            self.config.get("storage_namespace", "data"),
            "images",
        )

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

    def _find_image_file(
        self,
        images_dir: str,
        account_name: str,
        img_id: str,
    ) -> Optional[str]:
        if os.path.isabs(img_id) and os.path.isfile(img_id):
            return img_id
        matches = glob.glob(os.path.join(images_dir, account_name, f"{img_id}.*"))
        image_files = [path for path in matches if not path.endswith(".json")]
        return image_files[0] if image_files else None

    def _find_file(
        self,
        images_dir: str,
        account_name: str,
        file_id: str,
    ) -> Optional[str]:
        if os.path.isabs(file_id) and os.path.isfile(file_id):
            return file_id
        return self._find_image_file(images_dir, account_name, file_id)

    @staticmethod
    def _guess_mime_from_path(path: str) -> str:
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(os.path.splitext(path)[1].lower(), "application/octet-stream")

    def _get_context_state(
        self,
        account_name: str,
        context_name: str,
    ) -> Optional[Any]:
        """Memory seam overridden by CoALAPromptBuilder."""
        return None

    def _get_context_text(self, account_name: str, context_name: str) -> str:
        ctx = self._get_context_state(account_name, context_name)
        if ctx is None:
            return ""

        parts: List[str] = []
        header_parts: List[str] = []
        ctx_id = getattr(ctx, "id", None)
        if isinstance(ctx_id, str) and ctx_id.strip():
            header_parts.append(f"id: {ctx_id.strip()}")
        ctx_account = getattr(ctx, "account_name", None)
        if isinstance(ctx_account, str) and ctx_account.strip():
            header_parts.append(f"account_name: {ctx_account.strip()}")
        tag = getattr(ctx, "tag", None)
        if isinstance(tag, str) and tag.strip():
            header_parts.append(f"tag: {tag.strip()}")
        if header_parts:
            parts.append("\n".join(header_parts))

        resolved = getattr(ctx, "resolved_text", None)
        if isinstance(resolved, str) and resolved.strip():
            parts.append(resolved)
        return "\n\n".join(parts)

    def _ensure_current_query(
        self,
        messages: List[Dict[str, Any]],
        current_query: Any,
    ) -> List[Dict[str, Any]]:
        if not messages:
            return [{"role": "user", "content": current_query}]
        last = messages[-1]
        if last.get("role") == "user":
            last_content = last.get("content")
            if isinstance(last_content, list):
                text_parts = [
                    part.get("text", "")
                    for part in last_content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                combined = "".join(text_parts)
                if combined == current_query or (not current_query and combined):
                    return messages
            elif isinstance(last_content, str) and last_content == current_query:
                return messages
        return messages + [{"role": "user", "content": current_query}]

    def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str:
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
