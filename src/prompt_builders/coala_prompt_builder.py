from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from src.coala_memory.episodic import EpisodicMemoryRequest, EpisodicMemoryResult
from src.coala_memory.procedural import (
    ProceduralMemory,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
)
from src.prompt_builders.prompt_builder import (
    CONVERSATION_EVENT_KINDS,
    PromptBuilder,
)


class CoALAPromptBuilder(PromptBuilder):
    """PromptBuilder with all prompt-time memory retrieval routed through CoALA."""

    def __init__(
        self,
        *args: Any,
        procedural_memory: Optional[ProceduralMemory] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.procedural_memory = procedural_memory
        self._procedural_cache: Dict[Tuple[str, str], Optional[Any]] = {}
        self._current_query = ""
        self._current_episodic_result: Optional[EpisodicMemoryResult] = None

    def build_prompt(self, *args: Any, **kwargs: Any):
        self._procedural_cache = {}
        self._current_query = str(kwargs.get("content_text") or "")
        self._current_episodic_result = None
        return super().build_prompt(*args, **kwargs)

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

        active_session_id = (
            ""
            if not conversation_id or conversation_id in ("none", "new")
            else conversation_id
        )
        try:
            result = self.episodic_memory.recall(
                EpisodicMemoryRequest(
                    account_name=account_name,
                    agent_name=agent_name,
                    conversation_id=active_session_id,
                    query=self._current_query,
                    max_events=max_events,
                    digest_top_k=3,
                    digest_max_chars=3000,
                    event_kinds=list(CONVERSATION_EVENT_KINDS),
                    include_session_metadata=bool(active_session_id),
                    include_recent_history=bool(active_session_id),
                    include_archived_digests=True,
                )
            )
            self._current_episodic_result = result
            return result
        except Exception as ex:
            logging.warning(
                "CoALAPromptBuilder: episodic recall failed for session %s account=%s agent=%s: %s",
                conversation_id,
                account_name,
                agent_name,
                ex,
            )
            self._current_episodic_result = None
            return None

    def _load_digest_contexts(
        self,
        *,
        content_text: str,
        account_name: str,
        agent_name: str,
    ) -> list[dict[str, Any]]:
        result = self._current_episodic_result
        if result is None:
            return []
        return [
            {
                "session_id": digest.session_id,
                "snippet": digest.snippet,
                "truncated": digest.truncated,
                "score": digest.score,
            }
            for digest in result.digests
        ]

    def _save_overflow_digest(
        self,
        *,
        account_name: str,
        conversation_id: str,
        new_snippet: str,
    ) -> Optional[str]:
        if self.episodic_memory is None:
            return None
        return self.episodic_memory.save_overflow_digest(
            account_name=account_name,
            conversation_id=conversation_id,
            snippet=new_snippet,
        )

    def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]:
        if self.procedural_memory is None:
            return None
        if not context_name or context_name == "none":
            return None

        key = (account_name, context_name)
        if key in self._procedural_cache:
            return self._procedural_cache[key]

        try:
            result = self.procedural_memory.recall(
                ProceduralMemoryRequest(
                    account_name=account_name,
                    context_name=context_name,
                    create_if_missing=True,
                    include_resolved_text=True,
                    include_skills=True,
                    include_required_tools=True,
                )
            )
            state = self._result_to_context_state(result)
            self._procedural_cache[key] = state
            return state
        except Exception as ex:
            logging.warning(
                "CoALAPromptBuilder: procedural recall failed for context %s account=%s: %s; returning no context",
                context_name,
                account_name,
                ex,
            )
            self._procedural_cache[key] = None
            return None

    @staticmethod
    def _result_to_context_state(result: ProceduralMemoryResult) -> Optional[Any]:
        if not result.context_id:
            return None

        extra = result.metadata.get("extra", {})
        if not isinstance(extra, dict):
            extra = {}

        resolved_skills = [
            SimpleNamespace(
                name=skill.name,
                text=skill.text,
                mandatory_tools=list(skill.mandatory_tools),
                extra=dict(skill.metadata),
            )
            for skill in result.skills
        ]

        return SimpleNamespace(
            id=result.context_id,
            account_name=result.account_name,
            tag=result.tag,
            text=result.text,
            resolved_text=result.resolved_text,
            imports=list(result.imports),
            resolved_skills=resolved_skills,
            missing_imports=list(result.missing_imports),
            required_tools=list(result.required_tools),
            search_namespaces=list(result.search_namespaces),
            extra=dict(extra),
        )


__all__ = ["CoALAPromptBuilder"]
