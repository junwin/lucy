from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent, SessionLinks

from .interface import (
    EpisodicDigest,
    EpisodicEvent,
    EpisodicMemory,
    EpisodicMemoryRequest,
    EpisodicMemoryResult,
)
from .management import (
    EpisodicMemoryManager,
    EpisodicSession,
    EpisodicSessionQuery,
)

DigestRecall = Callable[[EpisodicMemoryRequest], List[EpisodicDigest]]


class Chat2EpisodicMemory(EpisodicMemory, EpisodicMemoryManager):
    """CoALA episodic-memory adapter over Lucy's existing Chat2 facade.

    The adapter is backend-agnostic. Use :meth:`from_sqlite` to construct it
    with ``SqliteChat2Primitives``; the same class also works with the JSONL or
    in-memory Chat2 backends.

    Chat2 owns session/event persistence. Archived digest similarity search is
    intentionally optional because it is currently backed by Lucy's embedding
    subsystem rather than the Chat2 SQLite database.

    Curation is deliberately not implemented here. ``CurationEngine`` is an
    application service that consumes the neutral ``EpisodicMemoryManager``
    operations exposed by this adapter.
    """

    def __init__(
        self,
        chat2_store: Chat2Store,
        *,
        digests_root: str | Path | None = None,
        digest_recall: DigestRecall | None = None,
    ) -> None:
        self.chat2_store = chat2_store
        self.digests_root = Path(digests_root) if digests_root is not None else None
        self.digest_recall = digest_recall

    @classmethod
    def from_sqlite(
        cls,
        db_path: str | Path,
        *,
        digests_root: str | Path | None = None,
        digest_recall: DigestRecall | None = None,
    ) -> "Chat2EpisodicMemory":
        from src.chat2.sqlite.backend import SqliteChat2Primitives

        primitives = SqliteChat2Primitives(db_path)
        return cls(
            Chat2Store(primitives),
            digests_root=digests_root,
            digest_recall=digest_recall,
        )

    # ------------------------------------------------------------------
    # Prompt-time recall
    # ------------------------------------------------------------------

    def recall(self, request: EpisodicMemoryRequest) -> EpisodicMemoryResult:
        result = EpisodicMemoryResult()

        if request.include_session_metadata and request.conversation_id:
            meta = self.chat2_store.get_session(request.conversation_id)
            if meta is not None:
                result.session_id = meta.session_id
                result.session_user_id = meta.user_id
                result.session_account_name = meta.account_name
                result.session_agent_name = meta.agent_name
                result.session_context_name = meta.context_name or ""
                result.session_type = meta.session_type
                result.session_participants = list(meta.participants or [])
                result.session_friendly_name = meta.friendly_name or ""
                result.session_tags = list(meta.tags or [])
                result.session_updated_at = meta.updated_at
                result.metadata.update(meta.metadata or {})

        if request.include_recent_history and request.conversation_id:
            events = list(self.chat2_store.stream_events(request.conversation_id))
            if request.event_kinds:
                allowed_kinds = set(request.event_kinds)
                events = [event for event in events if event.kind in allowed_kinds]

            if request.max_events <= 0:
                selected: List[ChatEvent] = []
            else:
                selected = events[-request.max_events :]

            if request.token_budget is not None:
                remaining = max(0, request.token_budget)
                budgeted: List[ChatEvent] = []
                for event in reversed(selected):
                    payload = event.payload if isinstance(event.payload, str) else json.dumps(event.payload, ensure_ascii=False)
                    estimate = max(1, len(payload) // 4)
                    if budgeted and estimate > remaining:
                        break
                    budgeted.insert(0, event)
                    remaining = max(0, remaining - estimate)
                selected = budgeted

            result.dropped_event_count = max(0, len(events) - len(selected))
            result.events = [self._to_episodic_event(event) for event in selected]

        if request.include_archived_digests:
            if self.digest_recall is not None:
                result.digests = list(self.digest_recall(request))
            else:
                result.metadata["archived_digests"] = "not_configured"

        return result

    def save_overflow_digest(
        self,
        *,
        account_name: str,
        conversation_id: str,
        snippet: str,
    ) -> Optional[str]:
        if self.digests_root is None:
            return None

        account_dir = self.digests_root / account_name
        account_dir.mkdir(parents=True, exist_ok=True)
        path = account_dir / f"{conversation_id}_overflow.md"

        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="ignore").strip()
        combined = f"{existing}\n\n{snippet}".strip() if existing else snippet
        path.write_text(combined, encoding="utf-8")
        return combined

    # ------------------------------------------------------------------
    # Session lifecycle / storage primitives
    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        account_name: str,
        agent_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        context_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_type: str = "user",
        participants: Optional[List[str]] = None,
        links: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EpisodicSession:
        link_model = SessionLinks(**links) if links else None
        meta = self.chat2_store.create_session(
            user_id=user_id or account_name,
            account_name=account_name,
            agent_name=agent_name,
            session_id=session_id,
            friendly_name=friendly_name,
            context_name=context_name,
            tags=tags,
            session_type=session_type,
            participants=participants,
            links=link_model,
        )
        if metadata:
            meta = self.chat2_store.update_session(meta.session_id, metadata=metadata)
        return self._to_session(meta)

    def get_session(self, session_id: str, *, include_events: bool = True) -> Optional[EpisodicSession]:
        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return None
        events = list(self.chat2_store.stream_events(session_id)) if include_events else []
        return self._to_session(meta, events)

    def session_exists(self, session_id: str) -> bool:
        return self.chat2_store.session_exists(session_id)

    def list_sessions(self, query: EpisodicSessionQuery) -> List[EpisodicSession]:
        metas = self.chat2_store.list_sessions(
            account_name=query.account_name or None,
            agent_name=query.agent_name or None,
            limit=query.limit,
        )
        sessions: List[EpisodicSession] = []
        needle = query.query.lower().strip()
        for meta in metas:
            events: List[ChatEvent] = []
            if needle:
                events = list(self.chat2_store.stream_events(meta.session_id))
                if not any(needle in self._payload_text(event.payload).lower() for event in events):
                    continue
            sessions.append(self._to_session(meta, events if needle else None))
        return sessions

    def append_event(self, session_id: str, event: EpisodicEvent) -> EpisodicEvent:
        stored = self.chat2_store.add_event(session_id, self._to_chat_event(event))
        return self._to_episodic_event(stored)

    def add_events(self, session_id: str, events: List[EpisodicEvent]) -> List[EpisodicEvent]:
        chat_events = [self._to_chat_event(event) for event in events]
        stored = self.chat2_store.add_events(session_id, chat_events)
        return [self._to_episodic_event(event) for event in stored]

    def link_event(
        self,
        correlation_id: Optional[str],
        session_id: str,
        event_id: str,
    ) -> None:
        """Link an event to a correlation id in the Chat2 sidecar index.

        Delegates to the wrapped ``Chat2Store``. Falsy correlation ids
        (``None`` or ``""``) are a no-op there and never raise.
        """
        self.chat2_store.link_event(correlation_id, session_id, event_id)

    def update_session(self, session_id: str, patch: Dict[str, Any]) -> EpisodicSession:
        patch = dict(patch)
        if isinstance(patch.get("links"), dict):
            patch["links"] = SessionLinks(**patch["links"])
        meta = self.chat2_store.update_session(session_id, **patch)
        return self._to_session(meta)

    def reset_session(self, session_id: str) -> None:
        self.chat2_store.reset_events(session_id)

    def delete_session(self, session_id: str) -> None:
        self.chat2_store.delete_session(session_id)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @classmethod
    def _to_session(cls, meta: Any, events: Optional[List[ChatEvent]] = None) -> EpisodicSession:
        links = meta.links.model_dump() if getattr(meta, "links", None) is not None else {}
        return EpisodicSession(
            session_id=meta.session_id,
            account_name=meta.account_name,
            agent_name=meta.agent_name,
            user_id=meta.user_id,
            friendly_name=meta.friendly_name,
            context_name=meta.context_name,
            session_type=meta.session_type,
            participants=list(meta.participants or []),
            links=links,
            created_at=meta.created_at,
            updated_at=meta.updated_at,
            tags=list(meta.tags or []),
            metadata=dict(meta.metadata or {}),
            events=[cls._to_episodic_event(event) for event in (events or [])],
        )

    @staticmethod
    def _to_chat_event(event: EpisodicEvent) -> ChatEvent:
        """Convert an ``EpisodicEvent`` into a Chat2 ``ChatEvent``.

        This is the single conversion path shared by :meth:`append_event` and
        :meth:`add_events`. Field mapping is unchanged from the original inline
        construction in ``append_event``: exactly ``event_id`` / ``ts`` /
        ``role`` / ``actor`` / ``kind`` / ``payload`` / ``metadata``.

        ``event_id`` and ``ts`` are only forwarded when both are present,
        otherwise Chat2 generates them from its own defaults (a fresh UUID and
        the current UTC time).
        """
        if event.event_id and event.created_at:
            return ChatEvent(
                event_id=event.event_id,
                ts=event.created_at,
                role=event.role,
                actor=event.actor or event.role,
                kind=event.kind or ("user_message" if event.role == "user" else "assistant_message"),
                payload=event.content,
                metadata=event.metadata,
            )
        return ChatEvent(
            role=event.role,
            actor=event.actor or event.role,
            kind=event.kind or ("user_message" if event.role == "user" else "assistant_message"),
            payload=event.content,
            metadata=event.metadata,
        )

    @staticmethod
    def _to_episodic_event(event: ChatEvent) -> EpisodicEvent:
        return EpisodicEvent(
            role=event.role,
            content=event.payload,
            kind=event.kind,
            actor=event.actor,
            event_id=event.event_id,
            created_at=event.ts,
            metadata=dict(event.metadata or {}),
        )

    @staticmethod
    def _payload_text(payload: Any) -> str:
        return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)


__all__ = ["Chat2EpisodicMemory"]
