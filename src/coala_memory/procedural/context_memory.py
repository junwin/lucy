from __future__ import annotations

from typing import Optional

from src.storage.interfaces import ContextStore

from .interface import (
    ProceduralMemory,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
    ProceduralSkill,
)


class ContextProceduralMemory(ProceduralMemory):
    """CoALA procedural-memory adapter over Lucy's existing ContextStore.

    Import resolution remains owned by the storage layer. This adapter simply
    exposes the fully-resolved Context as provider-neutral procedural memory.
    """

    def __init__(self, context_store: ContextStore) -> None:
        self.context_store = context_store

    def recall(self, request: ProceduralMemoryRequest) -> ProceduralMemoryResult:
        if not request.context_name or request.context_name == "none":
            return ProceduralMemoryResult(
                account_name=request.account_name,
                metadata={"reason": "no_context"},
            )

        ctx = (
            self.context_store.get_or_create_context(
                request.account_name,
                request.context_name,
            )
            if request.create_if_missing
            else self.context_store.get_context(
                request.account_name,
                request.context_name,
            )
        )

        if ctx is None:
            return ProceduralMemoryResult(
                account_name=request.account_name,
                metadata={"reason": "context_not_found"},
            )

        skills = []
        if request.include_skills:
            skills = [
                ProceduralSkill(
                    name=skill.name,
                    text=skill.text,
                    mandatory_tools=list(skill.mandatory_tools or []),
                    metadata=dict(skill.extra or {}),
                )
                for skill in (ctx.resolved_skills or [])
            ]

        return ProceduralMemoryResult(
            context_id=ctx.id,
            account_name=ctx.account_name,
            tag=ctx.tag,
            text=ctx.text,
            resolved_text=ctx.resolved_text if request.include_resolved_text else "",
            imports=list(ctx.imports or []),
            skills=skills,
            missing_imports=list(ctx.missing_imports or []),
            required_tools=(
                list(ctx.required_tools or [])
                if request.include_required_tools
                else []
            ),
            search_namespaces=list(ctx.search_namespaces or []),
            metadata={
                "backend": type(self.context_store).__name__,
                "extra": dict(ctx.extra or {}),
                "updated_at": ctx.updated_at.isoformat() if ctx.updated_at else None,
            },
        )


__all__ = ["ContextProceduralMemory"]
