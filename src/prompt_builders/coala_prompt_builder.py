from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from src.coala_memory.procedural import (
    ProceduralMemory,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
)
from src.prompt_builders.prompt_builder import PromptBuilder


class CoALAPromptBuilder(PromptBuilder):
    """PromptBuilder with named-context retrieval routed through procedural memory."""

    def __init__(
        self,
        *args: Any,
        procedural_memory: Optional[ProceduralMemory] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.procedural_memory = procedural_memory
        self._procedural_cache: Dict[Tuple[str, str], Optional[Any]] = {}

    def build_prompt(self, *args: Any, **kwargs: Any):
        self._procedural_cache = {}
        return super().build_prompt(*args, **kwargs)

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
