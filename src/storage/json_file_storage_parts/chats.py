"""Chat-related helper functions extracted from JsonFileStorage.

This module contains pure functions that operate on the JsonFileStorage instance
passed as the first argument (self). Initially functions are duplicated from the
original implementation to avoid changing behavior. Later steps will switch the
class to delegate to these functions.

Keep this module free of heavy imports to avoid circular dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.storage.models import ChatMessage, ChatSession


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    """Parse ISO timestamps into an aware UTC datetime (small local copy).

    Accepts strings with trailing Z, explicit offset, or naive timestamps
    (assumed UTC).
    """

    if not dt_str:
        return _now_utc()

    s = str(dt_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _chat_dict_to_session(self, data: Dict[str, Any]) -> ChatSession:
    """Convert stored JSON dict -> ChatSession dataclass.

    Signature mirrors the original method: self is the JsonFileStorage instance.
    """

    messages = [
        ChatMessage(
            role=m["role"],
            content=m["content"],
            utc_timestamp=_parse_dt_utc(m.get("utc_timestamp", "")),
            metadata=m.get("metadata", {}),
        )
        for m in data.get("messages", [])
    ]

    return ChatSession(
        id=data["id"],
        account_name=data["account_name"],
        agent_name=data["agent_name"],
        friendly_name=data.get("friendly_name"),
        created_at=_parse_dt_utc(data.get("created_at", "")),
        updated_at=_parse_dt_utc(data.get("updated_at", "")),
        messages=messages,
        tags=data.get("tags", []),
        summary=data.get("summary"),
        importance_score=data.get("importance_score", 0.5),
        include_in_context=data.get("include_in_context", True),
        metadata=data.get("metadata", {}),
    )


def list_chat_sessions(
    self,
    account_name: str,
    agent_name: Optional[str] = None,
    limit: int = 50,
    before: Optional[datetime] = None,
) -> List[ChatSession]:
    """List chat sessions for an account (optionally filtered by agent)."""

    chat_dir = self.storage_paths.chats / account_name
    index_path = chat_dir / "index.json"
    index = self._load_json(index_path) or {}

    sessions: List[ChatSession] = []
    for session_id, meta in index.items():
        if agent_name and meta.get("agent_name") != agent_name:
            continue

        updated_at = _parse_dt_utc(meta.get("updated_at", ""))
        if before and updated_at >= before:
            continue

        session = get_chat_session(self, session_id)
        if session:
            sessions.append(session)

    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return sessions[:limit]


def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
    """Load a single chat session by id."""

    chats_root = self.storage_paths.chats
    if not chats_root.exists():
        return None

    for account_dir in chats_root.iterdir():
        if not account_dir.is_dir():
            continue

        index = self._load_json(account_dir / "index.json") or {}
        if session_id not in index:
            continue

        data = self._load_json(account_dir / f"{session_id}.json")
        if not data:
            return None
        return _chat_dict_to_session(self, data)

    return None


def find_chat_sessions_by_friendly_name(
    self,
    account_name: str,
    agent_name: str,
    friendly_name: str,
    limit: int = 20,
) -> List[ChatSession]:
    """Find sessions by friendly name (case-insensitive substring match)."""

    sessions = list_chat_sessions(
        self,
        account_name=account_name,
        agent_name=agent_name,
        limit=limit,
    )

    q = (friendly_name or "").strip().lower()
    if not q:
        return sessions

    matches = [
        s
        for s in sessions
        if (s.friendly_name or "").strip().lower().find(q) != -1
    ]
    return matches[:limit]
