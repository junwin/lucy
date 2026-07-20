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

from src.chat2.facade import Chat2Store
from src.chat2.prompt_slice import get_last_n_events

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


class PromptBuilder(PromptBuilderInterface):
    @inject
    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        chat2_store: Optional[Chat2Store] = None,
    ):
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.chat2_store = chat2_store

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
    ) -> List[Dict[str, Any]]:
        """Build the full prompt (list of messages) for a model call.

        Logging and error handling goals:
        - Log how many history messages and document snippets are included.
        - Log when no chat session is found for the given conversation_id.
        - Fail soft on context/document errors (warn and continue).
        """
        logging.info("PromptBuilder.build_prompt: context_type=%s", context_type)

        agent: Optional[Agent] = self.agent_manager.get_agent(agent_name)

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

                doc_contexts = get_document_context(
                    storage=self.storage,
                    account_name=account_name,
                    query=content_text,
                    kind="obsidian_note",
                    docs_tag=docs_tag,
                    limit=3,
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

        # --- Current user message ---
        has_attachments = bool(image_ids or file_ids)
        if has_attachments:
            content_parts: List[Dict[str, Any]] = [
                {"type": "text", "text": content_text}
            ]
            content_parts.extend(self._resolve_attachments(
                account_name=account_name,
                image_ids=image_ids,
                file_ids=file_ids,
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
            "attachments=%d",
            agent_name,
            account_name,
            conversation_id,
            context_type,
            context_name,
            len(history_messages),
            len(doc_contexts),
            attachment_count,
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

    def _resolve_attachments(
        self,
        *,
        account_name: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Resolve image_ids and file_ids into provider-agnostic content parts.

        Returns a list of content-part dicts in intermediate format:

            # Image part
            {"type": "image", "source": {"data": "<base64>", "mime_type": "image/png"}}

            # File part (resolved to text)
            {"type": "text", "text": "[File: report.pdf]\\n...extracted content..."}
        """
        parts: List[Dict[str, Any]] = []

        images_dir = self._build_images_dir()

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
        """
        account_dir = os.path.join(images_dir, account_name)
        pattern = os.path.join(account_dir, f"{img_id}.*")
        matches = glob.glob(pattern)
        # Filter out .json sidecar files
        img_files = [m for m in matches if not m.endswith(".json")]
        return img_files[0] if img_files else None

    def _find_file(self, images_dir: str, account_name: str, file_id: str) -> Optional[str]:
        """Find a general file by UUID in the account's directory.

        Currently delegates to _find_image_file (files live in same dir structure).
        """
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
