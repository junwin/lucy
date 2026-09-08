# src/prompt_builders/prompt_builder.py

import base64
import glob
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from injector import inject

from src.config_manager import ConfigManager
from src.agent import AgentManager, Agent
from src.agent.caps import resolve_effective_cap
from src.storage.base import Storage
from src.storage.interfaces import ContextStore, EmbeddingStore
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.utils.text_snippet_loader import load_text_snippet
from src.coala_memory.semantic import SemanticMemory, SemanticMemoryRequest
from src.coala_memory.episodic import EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult

from src.chat2.facade import Chat2Store
from src.chat2.prompt_slice import get_last_n_events, _CONVERSATION_KINDS

DEFAULT_PROMPT_BUDGET_TOKENS = 12000
PROMPT_BUDGET_SAFETY_MARGIN = 500

# Minimum cosine similarity score for a digest to be included as context.
DIGEST_SCORE_THRESHOLD = 0.25
DIGEST_SEARCH_NAMESPACES = ["digests"]

# Score threshold for embedding-based document retrieval.
DOC_EMBEDDING_SCORE_THRESHOLD = 0.25

# Soft max tokens for front-loaded context.
CONTEXT_TEXT_SOFT_MAX_TOKENS = 2000

# Default semantic namespaces when the active context does not specify any.
DEFAULT_SEARCH_NAMESPACES = ["external"]


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


class PromptBuilder(PromptBuilderInterface):
    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        chat2_store: Optional[Chat2Store] = None,
        embedding_facade=None,  # retained for archived-digest retrieval
        embedding_store: Optional[EmbeddingStore] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.chat2_store = chat2_store
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

        if conversation_id not in ("none", "new", ""):
            try:
                meta_agent_name = ""
                meta_context_name = ""
                meta_friendly_name = ""
                meta_updated_at = None

                if episodic_result is not None and episodic_result.session_id:
                    meta_agent_name = episodic_result.session_agent_name
                    meta_context_name = episodic_result.session_context_name
                    meta_friendly_name = episodic_result.session_friendly_name
                    meta_updated_at = episodic_result.session_updated_at
                elif self.chat2_store is not None:
                    meta = self.chat2_store.get_session(conversation_id)
                    if meta is not None:
                        meta_agent_name = meta.agent_name
                        meta_context_name = meta.context_name or ""
                        meta_friendly_name = meta.friendly_name or ""
                        meta_updated_at = meta.updated_at

                if meta_updated_at is not None:
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    secs = (now - meta_updated_at).total_seconds()
                    if secs < 60:
                        elapsed = f"{int(secs)}s ago"
                    elif secs < 3600:
                        elapsed = f"{int(secs / 60)}m ago"
                    elif secs < 86400:
                        elapsed = f"{int(secs / 3600)}h ago"
                    else:
                        elapsed = f"{int(secs / 86400)}d ago"

                    info = f"Session: agent={meta_agent_name or agent_name}"
                    ctx_name = meta_context_name or meta_friendly_name
                    if ctx_name:
                        info += f", context={ctx_name}"
                    info += f", last activity {elapsed} (timestamp: {meta_updated_at.isoformat()}Z)"
                    messages.append({"role": "system", "content": info})
                    system_text_parts.append(info)
            except Exception:
                pass

        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})
                system_text_parts.append(extra.strip())

        context_text = self._get_context_text(
            account_name=account_name,
            context_name=context_name,
        )

        try:
            soft_max = resolve_effective_cap(
                "context_text_soft_max_tokens",
                agent,
                self.config,
                CONTEXT_TEXT_SOFT_MAX_TOKENS,
            )
            ctx_tokens = estimate_tokens_from_text(context_text or "")
            if ctx_tokens > soft_max:
                allowed_chars = max(0, soft_max * 4)
                context_text = (context_text or "")[:allowed_chars]
                context_text += "\n\n[Context truncated due to token budget]"
                logging.info(
                    "PromptBuilder: truncated context_text to %d chars (soft_max=%d tokens) for account=%s context=%s",
                    len(context_text),
                    soft_max,
                    account_name,
                    context_name or "(none)",
                )
        except Exception:
            logging.exception("PromptBuilder: failed while enforcing context soft max")

        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Additional context for this conversation:\n{context_text}",
                }
            )

        context_data: Dict[str, Any] = {}
        if context_name and context_name != "none":
            ctx = self._get_context_state(
                account_name=account_name,
                context_name=context_name,
            )
            if ctx is not None:
                namespaces = getattr(ctx, "search_namespaces", None)
                if isinstance(namespaces, list):
                    context_data["search_namespaces"] = namespaces
                extra = getattr(ctx, "extra", None)
                if isinstance(extra, dict):
                    for key, value in extra.items():
                        context_data.setdefault(key, value)

        doc_contexts: List[Dict[str, Any]] = []
        if context_type in ("documents", "hybrid"):
            try:
                search_namespaces = context_data.get("search_namespaces") or DEFAULT_SEARCH_NAMESPACES
                if use_embeddings:
                    doc_contexts = self._get_semantic_memory_context(
                        query=content_text,
                        account_name=account_name,
                        namespaces=search_namespaces,
                        top_k=agent.max_prompt_documents if agent else 3,
                        max_chars=9000,
                    )
                else:
                    logging.info(
                        "PromptBuilder: agent=%s has use_embeddings disabled; semantic document recall skipped",
                        agent_name,
                    )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to load semantic document context for %s/%s: %s",
                    account_name,
                    agent_name,
                    ex,
                )

        obsidian_text = "\n\n".join(
            (ctx.get("snippet") or "") for ctx in doc_contexts
        ) if doc_contexts else ""

        digest_contexts: List[Dict[str, Any]] = []
        try:
            digest_contexts = self._get_digest_context(
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

        digest_text = "\n\n".join(
            (d.get("snippet") or "") for d in digest_contexts
        ) if digest_contexts else ""

        has_attachments = bool(image_ids or file_ids)
        if has_attachments:
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
            user_message = {"role": "user", "content": content_parts}
        else:
            user_message = {"role": "user", "content": content_text}

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

            history_messages: List[Dict[str, str]] = []
            overflow_digest_text = ""
            try:
                matching: List[Any] = []
                original_match_count = 0

                if episodic_result is not None:
                    matching = list(episodic_result.events)
                    original_match_count = len(matching) + episodic_result.dropped_event_count
                elif self.chat2_store is not None and conversation_id not in ("none", "new", ""):
                    if self.chat2_store.session_exists(conversation_id):
                        events = list(self.chat2_store.stream_events(conversation_id))
                        matching = [e for e in events if e.kind in _CONVERSATION_KINDS]
                        original_match_count = len(matching)

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
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: episodic history failed for session %s account=%s agent=%s: %s; returning empty history",
                    conversation_id,
                    account_name,
                    agent_name,
                    ex,
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

            if doc_contexts:
                doc_lines: List[str] = [
                    "The following Obsidian notes may be relevant to the user's question:"
                ]
                for idx, ctx in enumerate(doc_contexts, start=1):
                    title = ctx.get("title") or "(untitled)"
                    tags = ctx.get("tags") or []
                    snippet = ctx.get("snippet") or ""
                    truncated = ctx.get("truncated") or False
                    header = f"{idx}. Title: {title}"
                    if tags:
                        header += f" | Tags: {', '.join(tags)}"
                    doc_lines.append(header)
                    doc_lines.append(snippet)
                    if truncated:
                        doc_lines.append("[Note: content truncated]")
                    doc_lines.append("")
                messages.append({"role": "system", "content": "\n".join(doc_lines).strip()})

            if digest_contexts:
                digest_lines: List[str] = [
                    "The following archived chat session digests may be relevant:"
                ]
                for idx, dctx in enumerate(digest_contexts, start=1):
                    digest_lines.append(
                        f"{idx}. Session {dctx.get('session_id') or 'unknown'} "
                        f"(score: {dctx.get('score', 0):.3f})"
                    )
                    digest_lines.append(dctx.get("snippet") or "")
                    if dctx.get("truncated") or False:
                        digest_lines.append("[Digest truncated]")
                    digest_lines.append("")
                messages.append(
                    {"role": "system", "content": "\n".join(digest_lines).strip()}
                )

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

    def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str:
        if agent is None:
            return f"You are {agent_name}, a helpful assistant."

        parts: List[str] = []
        parts.append(agent.system_prompt or f"You are {agent_name}, a helpful assistant.")
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
                    event_kinds=list(_CONVERSATION_KINDS),
                    include_session_metadata=True,
                    include_recent_history=True,
                    include_archived_digests=False,
                )
            )
        except Exception as ex:
            logging.warning(
                "PromptBuilder: episodic recall failed for session %s account=%s agent=%s: %s; falling back to Chat2",
                conversation_id,
                account_name,
                agent_name,
                ex,
            )
            return None

    @staticmethod
    def _event_content(event: Any) -> str:
        value = getattr(event, "content", None)
        if value is None and hasattr(event, "payload"):
            value = event.payload
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
        use_markers = not supports_images
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

                if use_markers:
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

    def _get_chat_history_messages(
        self,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        max_conversations: int,
    ) -> List[Dict[str, str]]:
        """Compatibility helper for older direct PromptBuilder callers/tests."""
        if not conversation_id or conversation_id in ("none", "new") or max_conversations <= 0:
            return []
        if self.chat2_store is None:
            return []
        try:
            if not self.chat2_store.session_exists(conversation_id):
                return []
            selected = get_last_n_events(
                self.chat2_store.stream_events(conversation_id),
                max_conversations,
            )
            return [
                {
                    "role": event.role,
                    "content": event.payload if isinstance(event.payload, str) else str(event.payload),
                }
                for event in selected
            ]
        except Exception as ex:
            logging.warning(
                "PromptBuilder: chat2 history failed for session %s account=%s agent=%s: %s; returning empty history",
                conversation_id,
                account_name,
                agent_name,
                ex,
            )
            return []

    def _get_context_state(
        self,
        account_name: str,
        context_name: str,
    ) -> Optional[Any]:
        """Compatibility context accessor; CoALAPromptBuilder overrides this."""
        if not context_name or context_name == "none":
            return None
        try:
            store: ContextStore = self.storage
            return store.get_or_create_context(account_name, context_name)
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load/create context %s for %s: %s",
                context_name,
                account_name,
                ex,
            )
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
