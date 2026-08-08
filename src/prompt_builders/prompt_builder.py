# src/prompt_builders/prompt_builder.py

import base64
import glob
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from injector import inject

from src.config_manager import ConfigManager
from src.agent import AgentManager, Agent
from src.storage.base import Storage
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.utils.document_context import get_document_context
from src.utils.text_snippet_loader import load_text_snippet

from src.chat2.facade import Chat2Store
from src.chat2.prompt_slice import get_last_n_events

DEFAULT_PROMPT_BUDGET_TOKENS = 12000

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

        system_message = self._build_agent_system_message(agent_name, agent)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]

        # --- Inject conversation_id so the agent can reference it ---
        if conversation_id and conversation_id not in ("none", "new"):
            messages.append({
                "role": "system",
                "content": f"Current session ID: {conversation_id}",
            })

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
            except Exception:
                # best-effort: if session lookup fails, just skip the info line
                pass

        for extra in (extra_system_messages or []):
            if extra and extra.strip():
                messages.append({"role": "system", "content": extra.strip()})

        # --- Chat history ---
        max_prompt_conversations = agent.max_prompt_conversations if agent else 0
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
                # Read optional docs_tag from the context state if available.
                docs_tag: Optional[str] = None
                if context_name and context_name != "none":
                    ctx = self._get_context_state(account_name=account_name, context_name=context_name)
                    if ctx is not None:
                        data = getattr(ctx, "data", None)
                        if isinstance(data, dict):
                            tag_val = data.get("tag")
                            if isinstance(tag_val, str) and tag_val.strip():
                                docs_tag = tag_val.strip()

                logging.info("PromptBuilder.build_prompt: docs_tag=%s", docs_tag)

                if use_embeddings:
                    doc_contexts = self._get_document_embedding_context(
                        query=content_text,
                        account_name=account_name,
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

        # --- Digest embeddings ---
        digest_contexts: List[Dict[str, Any]] = []
        try:
            digest_contexts = self._get_digest_context(
                query=content_text,
                account_name=account_name,
                top_k=3,
                max_chars=3000,
            )
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
        except Exception as ex:
            logging.warning(
                "PromptBuilder: failed to load digest context for %s/%s: %s",
                account_name,
                agent_name,
                ex,
            )

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
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": content_text})

        messages = self._ensure_current_query(messages, content_text)

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

        If namespaces is None, auto-discovers all available embedding namespaces
        for the account (same as digest path). Documents and digests share the
        same embedding store — this method loads snippets from whatever matches,
        which callers can then present as "notes" or "documents" as appropriate.
        """
        if self.embedding_facade is None:
            logging.info(
                "PromptBuilder._get_document_embedding_context: "
                "no embedding_facade — returning empty"
            )
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
                    "PromptBuilder._get_document_embedding_context: "
                    "auto-discovered namespaces=%s",
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
        """Load context text from storage, including any imported skills.

        Context is expected to be a ContextState with a free-form data dict.

        If the context frontmatter contains an 'imports' list, each entry names
        a skill file at skills/<account>/<name>.md. Skill texts are prepended
        before the main context body.

        Behavior:
        - If context_name is missing/"none": return empty string.
        - If context is missing in storage: create it immediately (empty defaults)
          and return empty string.
        - If context exists: prepend skill texts, then return data["text"].
        """
        ctx = self._get_context_state(account_name, context_name)
        if ctx is None:
            return ""

        data = getattr(ctx, "data", None)
        if not isinstance(data, dict):
            return ""

        parts: List[str] = []

        # --- Load imported skills ---
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
