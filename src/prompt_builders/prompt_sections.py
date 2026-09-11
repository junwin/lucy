from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.agent import Agent
from src.coala_memory.episodic import EpisodicMemoryResult


class PromptSections:
    """Render provider-neutral prompt sections without retrieval or budgeting."""

    @staticmethod
    def append_session_info(
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
            ctx_name = episodic_result.session_context_name or episodic_result.session_friendly_name
            if ctx_name:
                info += f", context={ctx_name}"
            info += f", last activity {elapsed} (timestamp: {updated_at.isoformat()}Z)"
            messages.append({"role": "system", "content": info})
            system_text_parts.append(info)
        except Exception:
            return

    @staticmethod
    def append_document_contexts(
        messages: List[Dict[str, Any]], doc_contexts: List[Dict[str, Any]]
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

    @staticmethod
    def append_digest_contexts(
        messages: List[Dict[str, Any]], digest_contexts: List[Dict[str, Any]]
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

    @staticmethod
    def build_agent_system_message(agent_name: str, agent: Optional[Agent]) -> str:
        if agent is None:
            return f"You are {agent_name}, a helpful assistant."
        parts: List[str] = [agent.system_prompt or f"You are {agent_name}, a helpful assistant."]
        if agent.persona:
            parts.append(agent.persona)
        if agent.style_prompt:
            parts.append(agent.style_prompt)
        return "\n\n".join(parts)

    @staticmethod
    def context_text(ctx: Optional[Any]) -> str:
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

    @staticmethod
    def ensure_current_query(
        messages: List[Dict[str, Any]], current_query: Any
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
