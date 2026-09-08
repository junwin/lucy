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
    """PromptBuilder with procedural context retrieval routed through CoALA.

    The base PromptBuilder already routes semantic and episodic retrieval through
    CoALA interfaces. This subclass completes the prompt-time memory boundary for
    named contexts while deliberately reusing the existing prompt composition,
    formatting, and token-budget code unchanged.

    A procedural recall is cached for the duration of one ``build_prompt`` call
    because the legacy builder asks for context text and context metadata in two
    separate helper calls.
    """

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
        # Scope procedural recall caching to a single prompt build so a context
        # changed between requests is reloaded on the next request.
        self._procedural_cache = {}
        return super().build_prompt(*args, **kwargs)

    def _get_context_state(self, account_name: str, context_name: str) -> Optional[Any]:
        if self.procedural_memory is None:
            return super()._get_context_state(account_name, context_name)
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
                "CoALAPromptBuilder: procedural recall failed for context %s account=%s: %s; "
                "falling back to ContextStore",
                context_name,
                account_name,
                ex,
            )
            state = super()._get_context_state(account_name, context_name)
            self._procedural_cache[key] = state
            return state

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

        # Present the same small surface PromptBuilder historically consumed
        # from storage.Context. The procedural result remains the canonical
        # retrieval contract; this proxy is only a compatibility seam for the
        # unchanged prompt-rendering code.
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
