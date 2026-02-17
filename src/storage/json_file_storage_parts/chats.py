"""Chat-related helper functions extracted from JsonFileStorage.

This module contains pure functions that operate on the JsonFileStorage instance
passed as the first argument (self). Initially functions are duplicated from the
original implementation to avoid changing behavior. Later steps will switch the
class to delegate to these functions.

Keep this module free of heavy imports to avoid circular dependencies.
"""

from __future__ import annotations

import uuid
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


def create_chat_session(
    self,
    account_name: str,
    agent_name: str,
    friendly_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> ChatSession:

    chat_id = str(uuid.uuid4())
    now = _now_utc()

    session = ChatSession(
        id=chat_id,
        account_name=account_name,
        agent_name=agent_name,
        friendly_name=friendly_name or f"Chat {chat_id[:8]}",
        created_at=now,
        updated_at=now,
        messages=[],
        tags=tags or [],
        summary=None,
        importance_score=0.5,
        include_in_context=True,
        metadata={},
    )

    chat_dir = self.storage_paths.chats / account_name
    self._ensure_dir(chat_dir)

    # Write JSON — Option A (sparse fields)
    chat_data: Dict[str, Any] = {
        "id": session.id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "messages": [],
        "tags": session.tags,
        "importance_score": session.importance_score,
        "include_in_context": session.include_in_context,
    }
    if session.summary is not None:
        chat_data["summary"] = session.summary
    if session.metadata:
        chat_data["metadata"] = session.metadata

    self._atomic_write(chat_dir / f"{chat_id}.json", chat_data)

    # Update index
    index_path = chat_dir / "index.json"
    index = self._load_json(index_path) or {}
    index[chat_id] = {
        "friendly_name": session.friendly_name,
        "agent_name": session.agent_name,
        "account_name": session.account_name,
        "updated_at": session.updated_at.isoformat(),
        "include_in_context": session.include_in_context,
    }
    self._atomic_write(index_path, index)

    return session

def rename_chat_session(self, session_id: str, friendly_name: str) -> None:
    """Backward-compatible API — delegates to update_chat_session()"""
    # Keep behavior identical to the original method on JsonFileStorage: use
    # the instance method update_chat_session which is still present on the
    # class at this stage of the refactor.
    self.update_chat_session(session_id, friendly_name=friendly_name)


def update_chat_session(
    self,
    session_id: str,
    *,
    friendly_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    summary: Optional[str] = None,
    importance_score: Optional[float] = None,
    include_in_context: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:

    session = self.get_chat_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    chat_path = (
        self.storage_paths.chats / session.account_name / f"{session_id}.json"
    )
    data = self._load_json(chat_path)
    if not data:
        raise ValueError(f"No stored data for session {session_id}")

    changed = False

    if friendly_name is not None:
        data["friendly_name"] = friendly_name
        changed = True

    if tags is not None:
        data["tags"] = tags
        changed = True

    if summary is not None:
        data["summary"] = summary
        changed = True

    if importance_score is not None:
        data["importance_score"] = importance_score
        changed = True

    if include_in_context is not None:
        data["include_in_context"] = include_in_context
        changed = True

    if metadata is not None:
        if metadata:
            data["metadata"] = metadata
        else:
            data.pop("metadata", None)  # Option A: remove empty
        changed = True

    if not changed:
        return

    data["updated_at"] = _now_utc().isoformat()
    self._atomic_write(chat_path, data)

    # Update index if friendly name changed
    if friendly_name is not None:
        index_path = (
            self.storage_paths.chats / session.account_name / "index.json"
        )
        index = self._load_json(index_path) or {}
        # Preserve existing structure if present, otherwise create new
        existing = index.get(session_id)
        if isinstance(existing, dict):
            existing["friendly_name"] = friendly_name
            existing["updated_at"] = data["updated_at"]
            index[session_id] = existing
        else:
            index[session_id] = {
                "friendly_name": friendly_name,
                "agent_name": session.agent_name,
                "account_name": session.account_name,
                "updated_at": data["updated_at"],
                "include_in_context": data.get("include_in_context", True),
            }
        self._atomic_write(index_path, index)

# ----------------------------------------------------------------------
# Functions moved from JsonFileStorage for write operations
# ----------------------------------------------------------------------

def append_chat_message(self, session_id: str, message: ChatMessage) -> None:
    """Append a ChatMessage to a stored chat JSON file."""
    session = get_chat_session(self, session_id)
    if not session:
        raise FileNotFoundError(f"Session {session_id} not found")

    chat_path = (
        self.storage_paths.chats / session.account_name / f"{session_id}.json"
    )
    data = self._load_json(chat_path)
    if not data:
        raise FileNotFoundError(f"Chat JSON missing for {session_id}")

    msg_ts = message.utc_timestamp or _now_utc()
    # Normalize to UTC-aware in case something passed a naive datetime
    if msg_ts.tzinfo is None:
        msg_ts = msg_ts.replace(tzinfo=timezone.utc)
    else:
        msg_ts = msg_ts.astimezone(timezone.utc)

    msg_data = {
        "role": message.role,
        "content": message.content,
        "utc_timestamp": msg_ts.isoformat(),
        "metadata": message.metadata,
    }

    data.setdefault("messages", []).append(msg_data)
    data["updated_at"] = _now_utc().isoformat()

    self._atomic_write(chat_path, data)


def delete_chat_session(self, session_id: str) -> None:
    """Delete a chat session and remove it from the per-account index.

    This is best-effort and idempotent: if the session or files are
    already gone, it will just return.
    """
    # First, locate the session to get account_name
    session = get_chat_session(self, session_id)
    if not session:
        # Nothing to do
        return

    account_name = session.account_name
    # Ensure we use the chats path provided by StoragePaths (was a bug previously)
    chat_dir = self.storage_paths.chats / account_name
    chat_path = chat_dir / f"{session_id}.json"

    # Remove the chat file if it exists
    try:
        if chat_path.exists():
            chat_path.unlink()
    except Exception as e:
        import logging

        logging.error("Failed to delete chat file %s: %s", chat_path, e)

    # Update index.json
    index_path = chat_dir / "index.json"
    index = self._load_json(index_path) or {}

    if session_id in index:
        index.pop(session_id, None)
        try:
            # If index becomes empty, you can either keep an empty file
            # or delete it. We'll keep an empty file for now.
            self._atomic_write(index_path, index)
        except Exception as e:
            import logging

            logging.error("Failed to update chat index %s: %s", index_path, e)
