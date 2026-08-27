"""
Module for defining data models used in the storage layer, including user profiles, context states, and references.

This module contains the following data classes:

- UserProfile: Represents a user account profile and preferences.
- Context: Represents shared state for a conversation.
- Skill: Represents a reusable Markdown skill file importable by a Context.
- DocumentRef: Represents a reference to a document.
- EmbeddingRecord: Represents a vector embedding with metadata.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---- User state ----

@dataclass
class UserProfile:
    """User account profile and preferences."""
    account_name: str
    full_name: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


# ---- Contexts ("whiteboards") ----

@dataclass
class Skill:
    """A reusable Markdown skill file (frontmatter + body).

    Skills are imported by contexts (single-level imports only). ``text`` is
    the skill body with any YAML frontmatter stripped; ``mandatory_tools`` are
    the tool handlers declared in the skill's frontmatter; ``extra`` is a
    catch-all for any other frontmatter keys.
    """
    name: str
    text: str = ""
    mandatory_tools: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Shared state/whiteboard for a conversation.

    Persisted fields (serialized to YAML frontmatter + body):
      - ``id`` / ``account_name``: derived from the storage path (filename
        stem + account directory).
      - ``tag``, ``imports``, ``mandatory_tools``, ``search_namespaces``,
        ``updated_at``: YAML frontmatter keys.
      - ``text``: the Markdown body (never frontmatter).
      - ``extra``: catch-all dict for unknown / legacy frontmatter keys.

    Computed / non-persisted members (populated at load time by storage):
      - ``resolved_skills`` / ``missing_imports``
      - ``resolved_text`` (property), ``required_tools`` (property)

    ``resolved_text`` and ``required_tools`` are derived and must never be
    serialized by ``save_context()``.
    """
    id: str
    account_name: str
    updated_at: datetime
    text: str = ""
    tag: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    mandatory_tools: List[str] = field(default_factory=list)
    search_namespaces: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # Computed at load time by storage; never persisted.
    resolved_skills: List[Skill] = field(default_factory=list)
    missing_imports: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Ensure timestamp is set."""
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)

    @property
    def resolved_text(self) -> str:
        """Fully-resolved context text: intrinsic body + imported skill bodies.

        Each resolved skill is appended under a ``## skill: <name>`` heading,
        matching the format previously produced by the context handler.
        """
        parts: List[str] = []
        body = (self.text or "").strip()
        if body:
            parts.append(body)
        for skill in self.resolved_skills:
            name = (skill.name or "").strip()
            text = (skill.text or "").strip()
            if text:
                parts.append(f"## skill: {name}\n{text}")
        return "\n\n".join(parts)

    @property
    def required_tools(self) -> List[str]:
        """Order-preserving dedupe of ``mandatory_tools`` + resolved skills' tools.

        Additive merge: the context's own declared tools first, then each
        resolved skill's ``mandatory_tools`` in import order. First occurrence
        wins; the context does not override imported requirements.
        """
        accumulated: List[str] = list(self.mandatory_tools)
        for skill in self.resolved_skills:
            accumulated.extend(skill.mandatory_tools)
        return _order_preserving_dedupe(accumulated)

    def to_data(self) -> Dict[str, Any]:
        """Return the persisted fields as a dict (e.g. for tool responses)."""
        return {
            "id": self.id,
            "account_name": self.account_name,
            "tag": self.tag,
            "imports": list(self.imports),
            "mandatory_tools": list(self.mandatory_tools),
            "search_namespaces": list(self.search_namespaces),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "text": self.text,
            "extra": dict(self.extra),
        }


def _order_preserving_dedupe(items: List[str]) -> List[str]:
    """Dedupe a list of strings, preserving first-occurrence order."""
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


# ---- Documents (Obsidian, static text, etc.) ----

@dataclass
class DocumentRef:
    """Reference to a document (metadata only, not content)."""
    id: str
    account_name: str
    path: str
    kind: str
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---- Embeddings ----

@dataclass
class EmbeddingRecord:
    """A vector embedding with metadata."""
    id: str
    namespace: str
    account_name: str
    vector: List[float]
    source_type: str
    source_id: str
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
