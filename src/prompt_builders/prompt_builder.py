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
from src.storage.base import Storage
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.utils.document_context import get_document_context
from src.utils.text_snippet_loader import load_text_snippet

from src.chat2.facade import Chat2Store
from src.chat2.prompt_slice import get_last_n_events, _CONVERSATION_KINDS

DEFAULT_PROMPT_BUDGET_TOKENS = 12000
PROMPT_BUDGET_SAFETY_MARGIN = 500

DEFAULT_SOURCE_BUDGETS = {
    "agent": 0.4,
    "account": 0.4,
    "context": 0.2,
}

# Minimum cosine similarity score for a digest to be included as context.
# Derived from Step 3a evaluation: positive queries ≥0.29, negatives ≤0.18.
DIGEST_SCORE_THRESHOLD = 0.25

# Score threshold for embedding-based document retrieval.
DOC_EMBEDDING_SCORE_THRESHOLD = 0.25

# Soft max tokens for front-loaded context (can be overridden by env/config)
CONTEXT_TEXT_SOFT_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS", "2000"))

# Default embedding namespaces to search when no context specifies them.
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
        embedding_facade=None,  # Optional[EmbeddingFacade] — lazy import
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.chat2_store = chat2_store
        self.embedding_facade = embedding_facade
        # last prompt breakdown for instrumentation by processors
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
        """Build the full prompt (list of messages) for a model call.

        Logging and error handling goals:
        - Log how many history messages and document snippets are included.
        - Log when no chat session is found for the given conversation_id.
        - Fail soft on context/document errors (warn and continue).
        """
        logging.info("PromptBuilder.build_prompt: context_type=%s", context_type)

        agent: Optional[Agent] = self.agent_manager.get_agent(agent_name)
        use_embeddings: bool = bool(agent and agent.use_embeddings)

        # Resolve context name: runtime override wins, otherwise use agent default
        if not context_name and agent is not None:
            resolved = getattr(agent, "default_context", None)
            if resolved:
                context_name = str(resolved).strip() or ""

        system_message = self._build_agent_system_message(agent_name, agent)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]

        # keep a textual copy of system/session messages for token accounting
        system_text_parts: List[str] = [system_message]

        # --- Inject conversation_id so the agent can reference it ---
        if conversation_id and conversation_id not in ("none", "new"):
            session_info_msg = (
                f"Current session ID: {conversation_id}"
            )
            messages.append({"role": "system", "content": session_info_msg})
            system_text_parts.append(session_info_msg)

        # --- Session info: agent, context, elapsed time ---
        if self.chat2_store is not None and conversation_id not in ("none", "new", ""):
            try:
                meta = self.chat2_store.get_session(conversation_id)
                if meta is not None:
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    delta = now - meta.updated_at
                    secs = delta.total_seconds()

                    if secs < 60:
                        elapsed = f"{int(secs)}s ago"
                    elif secs < 3600:
                        elapsed = f"{int(secs / 60)}m ago"
                    elif secs < 86400:
                        elapsed = f"{int(secs / 3600)}h ago"
                    else:
                        elapsed = f"{int(secs / 86400)}d ago"

                    info = f"Session: agent={meta.agent_name}"
                    ctx_name = meta.context_name or meta.friendly_name
                    if ctx_name:
                        info += f", context={ctx_name}"
                    info += f", last activity {elapsed} (timestamp: {meta.updated_at.isoformat()}Z)"

                    messages.append({"role": "system", "content": info})
                    system_text_parts.append(info)
            except Exception:
                # best-effort: if session lookup fails, just skip the info line
                pass

        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})
                system_text_parts.append(extra.strip())

        # --- Named context (from storage) ---
        context_text = self._get_context_text(account_name=account_name, context_name=context_name)

        # Enforce soft max for front-loaded context by truncating the text when it
        # exceeds the configured soft maximum. This reduces prompt size early and
        # prevents huge contexts from pushing history out of the budget.
        try:
            soft_max = self._get_context_soft_max_tokens()
            ctx_tokens = estimate_tokens_from_text(context_text or "")
            if ctx_tokens > soft_max:
                # Approximate character budget (estimate_tokens uses len//4)
                allowed_chars = max(0, soft_max * 4)
                context_text = (context_text or "")[:allowed_chars]
                context_text = context_text + "\n\n[Context truncated due to token budget]"
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

        # --- Read context data for search_namespaces and docs_tag ---
        context_data: Dict[str, Any] = {}
        if context_name and context_name != "none":
            ctx = self._get_context_state(account_name=account_name, context_name=context_name)
            if ctx is not None:
                data = getattr(ctx, "data", None)
                if isinstance(data, dict):
                    context_data = data

        # --- External documents ---
        doc_contexts: List[Dict[str, Any]] = []
        if context_type in ("documents", "hybrid"):
            try:
                # Read optional docs_tag from the context state if available.
                docs_tag: Optional[str] = None
                if isinstance(context_data.get("tag"), str) and context_data["tag"].strip():
                    docs_tag = context_data["tag"].strip()

                logging.info("PromptBuilder.build_prompt: docs_tag=%s", docs_tag)

                # Read search_namespaces from context, fall back to default
                search_namespaces = context_data.get("search_namespaces")
                if not search_namespaces:
                    search_namespaces = DEFAULT_SEARCH_NAMESPACES

                if use_embeddings:
                    doc_contexts = self._get_document_embedding_context(
                        query=content_text,
                        account_name=account_name,
                        namespaces=search_namespaces,
                        top_k=agent.max_prompt_documents if agent else 3,
                        max_chars=9000,
                    )
                else:
                    doc_contexts = get_document_context(
                        storage=self.storage,
                        account_name=account_name,
                        query=content_text,
                        kind="obsidian_note",
                        docs_tag=docs_tag,
                        limit=agent.max_prompt_documents if agent else 3,
                        max_chars=9000,
                    )

            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to load document context for %s/%s: %s",
                    account_name,
                    agent_name,
                    ex,
                )

        # build obsidian notes text for token accounting
        obsidian_text = "\n\n".join((ctx.get("snippet") or "") for ctx in doc_contexts) if doc_contexts else ""

        # --- Digest embeddings ---
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

        # build digest text for token accounting
        digest_text = "\n\n".join((d.get("snippet") or "") for d in digest_contexts) if digest_contexts else ""

        # --- Current user message ---
        has_attachments = bool(image_ids or file_ids)
        if has_attachments:
            content_parts: List[Dict[str, Any]] = [
                {"type": "text", "text": content_text}
            ]
            agent_allowed_tools = agent.allowed_tools if agent else None
            content_parts.extend(self._resolve_attachments(
                account_name=account_name,
                image_ids=image_ids,
                file_ids=file_ids,
                agent_allowed_tools=agent_allowed_tools,
                supports_images=supports_images,
            ))
            user_message = {"role": "user", "content": content_parts}
        else:
            user_message = {"role": "user", "content": content_text}

        # --- Token accounting instrumentation ---
        try:
            system_text = "\n\n".join(system_text_parts)
            system_tokens = estimate_tokens_from_text(system_text)
            context_tokens = estimate_tokens_from_text(context_text or "")
            obsidian_tokens = estimate_tokens_from_text(obsidian_text or "")
            digest_tokens = estimate_tokens_from_text(digest_text or "")
            user_tokens = estimate_tokens_from_text(content_text or "")


            # Soft-max warning for front-loaded context
            try:
                soft_max = self._get_context_soft_max_tokens()
                if context_tokens > soft_max:
                    logging.warning(
                        "PromptBuilder: context text (%d tokens) exceeds soft max (%d tokens) \\u2014 "
                        "agent=%s account=%s context=%s; consider trimming the context file",
                        context_tokens,
                        soft_max,
                        agent_name,
                        account_name,
                        context_name or "(none)",
                    )
            except Exception:
                logging.exception("PromptBuilder: failed to check context soft max")

            # Resolve ceiling (order: env, config, module default)
            ceiling = None
            env_val = os.getenv("PROMPT_BUDGET_MAX_TOKENS")
            if env_val:
                try:
                    ceiling = int(env_val)
                except Exception:
                    logging.warning("PromptBuilder: invalid PROMPT_BUDGET_MAX_TOKENS=%s; ignoring", env_val)

            if ceiling is None:
                try:
                    cfg_val = None
                    if hasattr(self.config, "get"):
                        cfg_val = self.config.get("prompt_budget_max_tokens", None)
                    if cfg_val is not None:
                        ceiling = int(cfg_val)
                except Exception:
                    logging.debug("PromptBuilder: failed to read prompt budget ceiling from config; using default")

            if ceiling is None:
                ceiling = DEFAULT_PROMPT_BUDGET_TOKENS

            # Safety margin: module constant (not configurable)
            safety_margin = PROMPT_BUDGET_SAFETY_MARGIN

            # Calculate history budget
            history_budget = ceiling - system_tokens - context_tokens - obsidian_tokens - digest_tokens - user_tokens - safety_margin

            logging.info(
                "PromptBuilder.history_budget: ceiling=%d system=%d context=%d obsidian=%d digest=%d user=%d safety_margin=%d -> history_budget=%d",
                ceiling,
                system_tokens,
                context_tokens,
                obsidian_tokens,
                digest_tokens,
                user_tokens,
                safety_margin,
                history_budget,
            )

            # --- Chat history selection by tokens, capped by max_prompt_conversations ---
            history_messages: List[Dict[str, str]] = []
            overflow_digest_text: str = ""
            try:
                if self.chat2_store is not None and conversation_id not in ("none", "new", ""):
                    if self.chat2_store.session_exists(conversation_id):
                        events = list(self.chat2_store.stream_events(conversation_id))
                        # Filter to conversational kinds (user/assistant)
                        matching = [e for e in events if e.kind in _CONVERSATION_KINDS]

                        # Apply max_prompt_conversations as a hard event-count cap.
                        # 0 = no history. N = at most the last N events. Token budget
                        # still applies as a secondary limit within those N events.
                        max_convs = agent.max_prompt_conversations if agent else 6
                        original_match_count = len(matching)
                        if max_convs <= 0:
                            matching = []
                        else:
                            matching = matching[-max_convs:]

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

                        # Walk from most recent backward and pick messages until budget exhausted.
                        remaining = history_budget
                        included: List = []
                        for e in reversed(matching):
                            payload = e.payload if isinstance(e.payload, str) else str(e.payload)
                            tok = estimate_tokens_from_text(payload)
                            if remaining >= tok:
                                included.insert(0, e)
                                remaining -= tok
                            else:
                                # If nothing has been included yet, include the single large message
                                if not included:
                                    included.insert(0, e)
                                break

                        # Any messages in `matching` that are not in `included` are older and were dropped
                        included_set = set(id(x) for x in included)
                        dropped = [e for e in matching if id(e) not in included_set]

                        if dropped:
                            try:
                                dropped_texts = [e.payload if isinstance(e.payload, str) else str(e.payload) for e in dropped]
                                digest_snippet = self._summarize_overflow(dropped_texts)

                                saved_digest = self._save_overflow_digest(
                                    account_name=account_name,
                                    conversation_id=conversation_id,
                                    new_snippet=digest_snippet,
                                )

                                overflow_digest_text = saved_digest if saved_digest else digest_snippet
                                messages.append({"role": "system", "content": f"Earlier in this session:\n{overflow_digest_text}"})
                            except Exception as ex:
                                logging.warning(
                                    "PromptBuilder: failed to persist session digest for %s: %s",
                                    conversation_id,
                                    ex,
                                )

                        history_messages = [
                            {"role": e.role, "content": e.payload if isinstance(e.payload, str) else str(e.payload)}
                            for e in included
                        ]
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: chat2 history failed for session %s account=%s agent=%s: %s; returning empty history",
                    conversation_id,
                    account_name,
                    agent_name,
                    ex,
                )

            # Now assemble final messages: system messages already present in messages
            # Insert history after system messages
            messages.extend(history_messages)

            # --- Final token breakdown (after history selection) ---
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

            logging.info(
                "PromptBuilder.token_breakdown: agent=%s account=%s session=%s system=%d context=%d obsidian=%d digest=%d history=%d overflow=%d user=%d total=%d",
                agent_name,
                account_name,
                conversation_id,
                system_tokens,
                context_tokens,
                obsidian_tokens,
                digest_tokens,
                history_tokens,
                overflow_tokens,
                user_tokens,
                total_without_handlers,
            )

            # --- Append document contexts if any ---
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

            # --- Append digest contexts if any ---
            if digest_contexts:
                digest_lines: List[str] = [
                    "The following archived chat session digests may be relevant:",
                ]
                for idx, dctx in enumerate(digest_contexts, start=1):
                    session_id = dctx.get("session_id") or "unknown"
                    score = dctx.get("score", 0)
                    snippet = dctx.get("snippet") or ""
                    truncated = dctx.get("truncated") or False
                    digest_lines.append(
                        f"{idx}. Session {session_id} (score: {score:.3f})"
                    )
                    digest_lines.append(snippet)
                    if truncated:
                        digest_lines.append("[Digest truncated]")
                    digest_lines.append("")

                messages.append({"role": "system", "content": "\n".join(digest_lines).strip()})

            # Finally append the user message
            current_user_content = user_message["content"]
            # Use _ensure_current_query which handles both list and str content
            messages = self._ensure_current_query(messages, current_user_content)

            # --- Summary logging ---
            attachment_count = len(image_ids or []) + len(file_ids or [])
            logging.info(
                "PromptBuilder.build_prompt: agent=%s account=%s session_id=%s "
                "context_type=%s context_name=%s history_messages=%d docs_used=%d "
                "digest_docs_used=%d attachments=%d supports_images=%s use_embeddings=%s",
                agent_name,
                account_name,
                conversation_id,
                context_type,
                context_name,
                len(history_messages),
                len(doc_contexts),
                len(digest_contexts),
                attachment_count,
                supports_images,
                use_embeddings,
            )

        except Exception as ex:
            logging.exception("PromptBuilder: failed to compute token breakdown: %s", ex)

        return messages

    # --- helper methods ---

    def _build_agent_system_message(self, agent_name: str, agent: Optional[Agent]) -> str:
        """Combine system_prompt, persona, and style_prompt into one system message."""
        if agent is None:
            return f"You are {agent_name}, a helpful assistant."

        parts: List[str] = []
        if agent.system_prompt:
            parts.append(agent.system_prompt)
        else:
            parts.append(f"You are {agent_name}, a helpful assistant.")

        if agent.persona:
            parts.append(agent.persona)
        if agent.style_prompt:
            parts.append(agent.style_prompt)

        return "\n\n".join(parts)

    def _get_document_embedding_context(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 9000,
        score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search embedding store for relevant documents using semantic similarity.

        Similar to _get_digest_context but tuned for document retrieval:
        larger max_chars, different default threshold, and includes title/tags.

        Namespaces must be provided explicitly. If not, falls back to
        DEFAULT_SEARCH_NAMESPACES (["external"]).
        """
        if self.embedding_facade is None:
            logging.info(
                "PromptBuilder._get_document_embedding_context: "
                "no embedding_facade — returning empty"
            )
            return []

        if not query or not query.strip():
            return []

        if namespaces is None:
            namespaces = DEFAULT_SEARCH_NAMESPACES

        try:
            # Embed the user query
            resp = self.embedding_facade.embed(
                [query], model="text-embedding-3-small"
            )
            query_vector = resp.embeddings[0]

            logging.info(
                "PromptBuilder._get_document_embedding_context: "
                "searching namespaces=%s",
                namespaces,
            )

            results = self.storage.query_embeddings(
                namespaces=namespaces,
                account_name=account_name,
                query_vector=query_vector,
                top_k=top_k,
            )

            # Log raw results before threshold filtering
            query_preview = query[:120].replace("\n", " ")
            raw_summary = ", ".join(
                f"{r.source_id}={s:.3f}" for r, s in results
            )
            logging.info(
                "PromptBuilder._get_document_embedding_context: "
                "query='%s' top_k=%d raw=[%s]",
                query_preview,
                top_k,
                raw_summary,
            )

            contexts: List[Dict[str, Any]] = []

            for record, score in results:
                if score < score_threshold:
                    continue

                path = record.source_metadata.get("path") if record.source_metadata else None
                if not path:
                    continue

                snippet, truncated = load_text_snippet(path, max_chars=max_chars)
                if not snippet.strip():
                    continue

                title = record.source_metadata.get("title") or os.path.basename(path)
                tags = record.source_metadata.get("tags") or []

                contexts.append({
                    "title": title,
                    "tags": tags,
                    "snippet": snippet,
                    "truncated": truncated,
                    "score": score,
                    "source_id": record.source_id,
                })

            if contexts:
                selected_summary = ", ".join(
                    f"{c['source_id']}={c['score']:.3f}" for c in contexts
                )
                logging.info(
                    "PromptBuilder._get_document_embedding_context: selected=%d [%s]",
                    len(contexts),
                    selected_summary,
                )
            else:
                logging.info(
                    "PromptBuilder._get_document_embedding_context: "
                    "selected=0 (none above threshold %.2f)",
                    score_threshold,
                )

            return contexts

        except Exception as ex:
            logging.warning(
                "PromptBuilder._get_document_embedding_context: "
                "failed for account=%s: %s",
                account_name,
                ex,
            )
            return []

    def _get_digest_context(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 3000,
    ) -> List[Dict[str, Any]]:
        """Search embeddings across one or more namespaces and return relevant snippets.

        If namespaces is None, auto-discovers all available embedding namespaces
        for the account via storage.list_embedding_namespaces().
        """
        if self.embedding_facade is None:
            return []

        if not query or not query.strip():
            return []

        try:
            # Embed the user query
            resp = self.embedding_facade.embed(
                [query], model="text-embedding-3-small"
            )
            query_vector = resp.embeddings[0]

            # Auto-discover namespaces if not explicitly provided
            if namespaces is None:
                namespaces = self.storage.list_embedding_namespaces(account_name)
                logging.info(
                    "PromptBuilder._get_digest_context: auto-discovered namespaces=%s",
                    namespaces,
                )

            results = self.storage.query_embeddings(
                namespaces=namespaces,
                account_name=account_name,
                query_vector=query_vector,
                top_k=top_k,
            )

            # Log raw top_k results (before threshold filtering) for eval
            query_preview = query[:120].replace("\n", " ")
            raw_summary = ", ".join(
                f"{r.source_id}={s:.3f}" for r, s in results
            )
            logging.info(
                "PromptBuilder._get_digest_context: query='%s' top_k=%d raw=[%s]",
                query_preview,
                top_k,
                raw_summary,
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

                contexts.append({
                    "session_id": record.source_id,
                    "snippet": snippet,
                    "truncated": truncated,
                    "score": score,
                })

            # Log which digests passed the threshold
            if contexts:
                selected_summary = ", ".join(
                    f"{c['session_id']}={c['score']:.3f}" for c in contexts
                )
                logging.info(
                    "PromptBuilder._get_digest_context: selected=%d [%s]",
                    len(contexts),
                    selected_summary,
                )
            else:
                logging.info(
                    "PromptBuilder._get_digest_context: selected=0 (none above threshold %.2f)",
                    DIGEST_SCORE_THRESHOLD,
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
        """Resolve image_ids and file_ids into provider-agnostic content parts.

        When supports_images is False, images are emitted as text markers
        (image UUID + filename) instead of base64 data, so a text-only model
        can still see that images exist. A mandatory instruction is appended
        telling the agent to delegate image analysis via tasklists_manage +
        tasklists_run to a vision-capable worker (colin).

        File attachments are always inlined as text regardless.

        Returns a list of content-part dicts in intermediate format:

            # Image part (inline mode)
            {"type": "image", "source": {"data": "<base64>", "mime_type": "image/png"}}

            # Image part (marker mode)
            {"type": "text", "text": "[Attached image: <uuid> — foo.png]"}

            # File part (resolved to text)
            {"type": "text", "text": "[File: report.pdf]\\n...extracted content..."}
        """
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
                    filename = os.path.basename(img_path)
                    parts.append({
                        "type": "text",
                        "text": f"[Attached image: {img_id} — {filename}]",
                    })
                    any_image_marked = True

                    logging.info(
                        "PromptBuilder: marker for image_id=%s path=%s (supports_images=False)",
                        img_id,
                        img_path,
                    )
                else:
                    with open(img_path, "rb") as f:
                        raw = f.read()

                    b64 = base64.b64encode(raw).decode("ascii")
                    mime = self._guess_mime_from_path(img_path)

                    parts.append({
                        "type": "image",
                        "source": {
                            "data": b64,
                            "mime_type": mime,
                        },
                    })

                    logging.info(
                        "PromptBuilder: resolved image_id=%s path=%s size=%d mime=%s",
                        img_id,
                        img_path,
                        len(raw),
                        mime,
                    )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to resolve image_id=%s for account=%s: %s",
                    img_id,
                    account_name,
                    ex,
                )

        if any_image_marked:
            parts.append({
                "type": "text",
                "text": (
                    "Your model cannot see images. To analyze images: "
                    "create a tasklist via tasklists_manage (action='put') "
                    "with a task that includes the image UUIDs above in "
                    "meta.image_ids as a list of strings. "
                    "Example: \"meta\": {\"image_ids\": [\"<uuid>\"]}. "
                    "Then run it with tasklists_run (worker_agent='colin'). "
                    "Use the worker's output to answer the user."
                ),
            })

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

                # For now, read text files only; binary file handling deferred
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                except UnicodeDecodeError:
                    text = f"[Binary file: {os.path.basename(file_path)}]"

                parts.append({
                    "type": "text",
                    "text": f"[File: {os.path.basename(file_path)}]\n{text}",
                })

                logging.info(
                    "PromptBuilder: resolved file_id=%s path=%s",
                    file_id,
                    file_path,
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
        """Return the base images directory path from config."""
        storage_root = self.config.get("storage_root_path", "/home/junwin/lucy_storage")
        storage_ns = self.config.get("storage_namespace", "data")
        return os.path.join(storage_root, storage_ns, "images")

    def _build_digests_dir(self, account_name: str) -> Path:
        """Return the path to the account's digests directory.

        Uses the same convention as curation: data/digests/<account>/,
        resolved relative to the repo root (CWD).
        """
        return Path("data") / "digests" / account_name

    def _save_overflow_digest(
        self,
        *,
        account_name: str,
        conversation_id: str,
        new_snippet: str,
    ) -> Optional[str]:
        """Save an overflow digest to data/digests/<account>/<session_id>_overflow.md.

        Appends new_snippet to any existing digest for the same session.
        Returns the full digest text (existing + new) or the new snippet alone
        if the file couldn't be written.
        """
        digest_dir = self._build_digests_dir(account_name)
        digest_dir.mkdir(parents=True, exist_ok=True)

        output_path = digest_dir / f"{conversation_id}_overflow.md"

        existing = ""
        try:
            if output_path.exists():
                existing = output_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

        if existing:
            combined = existing + "\n\n" + new_snippet
        else:
            combined = new_snippet

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
        """Find an image file by UUID in the account's images directory.

        Looks for `{img_id}.*` — returns the first matching file path or None.
        If img_id is already a full, existing path, returns it directly.
        """
        # Defensive: if img_id is a full path that exists, use it directly
        if os.path.isabs(img_id) and os.path.isfile(img_id):
            return img_id

        account_dir = os.path.join(images_dir, account_name)
        pattern = os.path.join(account_dir, f"{img_id}.*")
        matches = glob.glob(pattern)
        # Filter out .json sidecar files
        img_files = [m for m in matches if not m.endswith(".json")]
        return img_files[0] if img_files else None

    def _find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str]:
        """Find a general file by UUID in the account's directory.

        If file_id is already a full, existing path, returns it directly.
        Otherwise delegates to _find_image_file (files live in same dir structure).
        """
        # Defensive: if file_id is a full path that exists, use it directly
        if os.path.isabs(file_id) and os.path.isfile(file_id):
            return file_id
        return self._find_image_file(images_dir, account_name, file_id)

    @staticmethod
    def _guess_mime_from_path(path: str) -> str:
        """Guess MIME type from file extension."""
        ext = os.path.splitext(path)[1].lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mapping.get(ext, "application/octet-stream")

    def _get_chat_history_messages(
        self,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        max_conversations: int,
    ) -> List[Dict[str, str]]:
        if not conversation_id or conversation_id in ("none", "new"):
            return []
        if max_conversations <= 0:
            return []

        # This method is kept for backward compatibility but is no longer used
        # in the token-based prompt budget flow. It mirrors the legacy behavior
        # of returning the last N conversation events.
        # --- Try chat2 only ---
        if self.chat2_store is not None:
            try:
                if self.chat2_store.session_exists(conversation_id):
                    events = self.chat2_store.stream_events(conversation_id)
                    selected = get_last_n_events(events, max_conversations)
                    if selected:
                        return [
                            {"role": e.role, "content": e.payload if isinstance(e.payload, str) else str(e.payload)}
                            for e in selected
                        ]
                    # Session exists but no matching events — return empty
                    return []
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: chat2 history failed for session %s account=%s agent=%s: %s; "
                    "returning empty history",
                    conversation_id,
                    account_name,
                    agent_name,
                    ex,
                )
                return []

        # No chat2 store configured — return empty history
        return []

    def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]:
        """Return the ContextState object (or None) for the named context.

        This follows the same fallback logic as _get_context_text: prefer a
        storage implementation that supports get_or_create_context, otherwise
        use get_context. Fail softly and return None on errors.
        """
        if not context_name or context_name == "none":
            return None

        try:
            if hasattr(self.storage, "get_or_create_context"):
                ctx = self.storage.get_or_create_context(account_name, context_name)
            else:
                ctx = self.storage.get_context(account_name, context_name)
            return ctx
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load/create context %s for %s: %s",
                context_name,
                account_name,
                ex,
            )
            return None

    def _get_context_text(self, account_name: str, context_name: str) -> str:
        """Render the context text block for the LLM prompt.

        Imports are processed: each named skill is loaded and its body prepended
        to the context. The operational directives themselves (the imports list,
        allowed_tools, search_namespaces) are never included in the prompt text.

        Behavior:
        - If context_name is missing/"none": return empty string.
        - If context is missing in storage: create it immediately (empty defaults)
          and return empty string.
        - If context exists: render an identity header (id, account_name, tag when
          present), then prepend imported skill texts, then the context body.
        """
        ctx = self._get_context_state(account_name, context_name)
        if ctx is None:
            return ""

        data = getattr(ctx, "data", None)
        if not isinstance(data, dict):
            return ""

        parts: List[str] = []

        # --- Identity header (content metadata only) ---
        header_parts: List[str] = []
        ctx_id = getattr(ctx, "id", None)
        if isinstance(ctx_id, str) and ctx_id.strip():
            header_parts.append(f"id: {ctx_id.strip()}")
        ctx_account = getattr(ctx, "account_name", None)
        if isinstance(ctx_account, str) and ctx_account.strip():
            header_parts.append(f"account_name: {ctx_account.strip()}")
        tag = data.get("tag")
        if isinstance(tag, str) and tag.strip():
            header_parts.append(f"tag: {tag.strip()}")
        if header_parts:
            parts.append("\n".join(header_parts))

        # --- Process imported skills (content, not the imports directive) ---
        imports = data.get("imports")
        if isinstance(imports, list):
            for skill_name in imports:
                if not isinstance(skill_name, str) or not skill_name.strip():
                    continue
                try:
                    skill_text = self.storage.get_skill_text(account_name, skill_name.strip())
                    if skill_text:
                        parts.append(skill_text)
                    else:
                        logging.warning(
                            "PromptBuilder: skill '%s' not found for account '%s'",
                            skill_name,
                            account_name,
                        )
                except Exception as ex:
                    logging.warning(
                        "PromptBuilder: failed to load skill '%s' for %s: %s",
                        skill_name,
                        account_name,
                        ex,
                    )

        # --- Main context body ---
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)

        return "\n\n".join(parts)

    def _ensure_current_query(self, messages: List[Dict[str, Any]], current_query: str) -> List[Dict[str, Any]]:
        if not messages:
            return [{"role": "user", "content": current_query}]
        last = messages[-1]
        if last.get("role") == "user":
            last_content = last.get("content")
            # Content might be a string or a content-part array
            if isinstance(last_content, list):
                text_parts = [p.get("text", "") for p in last_content if isinstance(p, dict) and p.get("type") == "text"]
                combined = "".join(text_parts)
                if combined == current_query or (not current_query and combined):
                    return messages
            elif isinstance(last_content, str) and last_content == current_query:
                return messages
        return messages + [{"role": "user", "content": current_query}]

    def _get_context_soft_max_tokens(self) -> int:
        """Resolve the soft max tokens for front-loaded context.

        Order of precedence:
          1. Environment variable PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS
          2. config.get('context_text_soft_max_tokens') if available
          3. module default (CONTEXT_TEXT_SOFT_MAX_TOKENS)

        Returns an int >= 0.
        """
        # 1) Check environment
        env_val = os.getenv("PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS")
        if env_val:
            try:
                v = int(env_val)
                if v >= 0:
                    return v
            except Exception:
                logging.warning(
                    "PromptBuilder: invalid PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS=%s; using fallback",
                    env_val,
                )

        # 2) Check config (ConfigManager-like object with .get)
        try:
            cfg_val = None
            if hasattr(self.config, "get"):
                cfg_val = self.config.get("context_text_soft_max_tokens", None)
            if cfg_val is not None:
                try:
                    v = int(cfg_val)
                    if v >= 0:
                        return v
                except Exception:
                    logging.warning(
                        "PromptBuilder: invalid context_text_soft_max_tokens in config: %s; using fallback",
                        cfg_val,
                    )
        except Exception:
            logging.debug("PromptBuilder: failed to read config for soft max tokens; using default")

        # 3) Fallback to module-level default
        return CONTEXT_TEXT_SOFT_MAX_TOKENS

    def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str:
        """Create a short human-readable digest from a list of earlier message texts.

        This is intentionally simple and deterministic: concatenate leading
        excerpts from the first few messages until max_chars is reached, and
        prepend a short header describing how many messages were summarized.
        """
        if not texts:
            return ""

        header = f"{len(texts)} earlier messages were summarized."
        out_parts: List[str] = [header]
        remaining = max_chars - len(header) - 2
        for t in texts:
            if remaining <= 0:
                break
            snippet = t.strip().replace("\n", " ")
            if not snippet:
                continue
            take = min(len(snippet), remaining)
            out_parts.append(snippet[:take])
            remaining -= take + 2
        combined = "\n\n".join(out_parts)
        if len(combined) > max_chars:
            combined = combined[: max_chars - 3] + "..."
        return combined
