# ==============================================================================
# FILE: src/storage/json_file_storage.py
# JSON-backed storage implementation for Lucy.
# ==============================================================================

import json
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.keywords import Keywords
 
from flask import sessions

from .base import Storage
from .models import (
    ChatMessage,
    ChatSession,
    UserProfile,
    AgentProfile,
    ContextState,
    DocumentRef,
    EmbeddingRecord,
)


def _now_utc() -> datetime:
    """Return an offset-aware datetime in UTC."""
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    """
    Parse ISO timestamps from storage into an aware UTC datetime.

    Accepts:
      - "2023-06-14T21:58:27.803580Z"
      - "2023-06-14T21:58:27.803580+00:00"
      - naive "2023-06-14T21:58:27.803580" (assumed UTC)
    """
    if not dt_str:
        return _now_utc()

    s = str(dt_str).strip()
    # Support trailing "Z" (Zulu time)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    # If naive, assume UTC; if aware, normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


class JsonFileStorage(Storage):
    """JSON-backed storage implementation for Lucy."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON atomically."""
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.warning("Failed to decode JSON from %s: %s", path, e)
            return None
        except Exception as e:
            logging.error("Unexpected error reading JSON from %s: %s", path, e)
            return None

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------------
    # Chat Sessions
    # ----------------------------------------------------------------------

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

        chat_dir = self.base_path / "chats" / account_name
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

    def find_chat_sessions_by_friendly_name(self, account_name: str, agent_name: str, friendly_name: str, limit: int = 20) -> List[ChatSession]:
        sessions = self.list_chat_sessions(account_name=account_name, agent_name=agent_name, limit=500)
        matches = [s for s in sessions if (s.friendly_name or "").lower() == friendly_name.lower()]
        return matches[:limit]

    # ----------------------------------------------------------------------

    def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        chats_dir = self.base_path / "chats"
        if not chats_dir.exists():
            return None

        for account_dir in chats_dir.iterdir():
            if not account_dir.is_dir():
                continue

            chat_path = account_dir / f"{session_id}.json"
            if chat_path.exists():
                data = self._load_json(chat_path)
                if data:
                    return self._chat_dict_to_session(data)

        return None

    # ----------------------------------------------------------------------

    def list_chat_sessions(
        self,
        account_name: str,
        agent_name: Optional[str] = None,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[ChatSession]:

        chat_dir = self.base_path / "chats" / account_name
        if not chat_dir.exists():
            return []

        # Normalize 'before' to aware UTC if provided
        if before is not None:
            if before.tzinfo is None:
                before = before.replace(tzinfo=timezone.utc)
            else:
                before = before.astimezone(timezone.utc)

        sessions: List[ChatSession] = []

        for chat_file in chat_dir.glob("*.json"):
            if chat_file.name == "index.json":
                continue

            data = self._load_json(chat_file)
            if not data:
                continue

            if agent_name and data.get("agent_name") != agent_name:
                continue

            if before:
                updated_at = _parse_dt_utc(data.get("updated_at", ""))
                if updated_at >= before:
                    continue

            sessions.append(self._chat_dict_to_session(data))

        # All updated_at are now aware UTC → safe to compare
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    # ----------------------------------------------------------------------

    def rename_chat_session(self, session_id: str, friendly_name: str) -> None:
        """Backward-compatible API — delegates to update_chat_session()"""
        self.update_chat_session(session_id, friendly_name=friendly_name)

    # ----------------------------------------------------------------------

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
            self.base_path / "chats" / session.account_name / f"{session_id}.json"
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
                self.base_path / "chats" / session.account_name / "index.json"
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

    def append_chat_message(self, session_id: str, message: ChatMessage) -> None:
        session = self.get_chat_session(session_id)
        if not session:
            raise FileNotFoundError(f"Session {session_id} not found")

        chat_path = (
            self.base_path / "chats" / session.account_name / f"{session_id}.json"
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

    # ----------------------------------------------------------------------

    def delete_chat_session(self, session_id: str) -> None:
        """Delete a chat session and remove it from the per-account index.

        This is best-effort and idempotent: if the session or files are
        already gone, it will just return.
        """
        # First, locate the session to get account_name
        session = self.get_chat_session(session_id)
        if not session:
            # Nothing to do
            return

        account_name = session.account_name
        chat_dir = self.base_path / "chats" / account_name
        chat_path = chat_dir / f"{session_id}.json"

        # Remove the chat file if it exists
        try:
            if chat_path.exists():
                chat_path.unlink()
        except Exception as e:
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
                logging.error("Failed to update chat index %s: %s", index_path, e)

    # ----------------------------------------------------------------------

    def _chat_dict_to_session(self, data: Dict[str, Any]) -> ChatSession:
        """Convert stored JSON dict → ChatSession dataclass."""

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

    # ----------------------------------------------------------------------
    # USER PROFILES
    # ----------------------------------------------------------------------

    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        path = self.base_path / "users" / f"{account_name}.json"
        data = self._load_json(path)
        if not data:
            return None

        return UserProfile(
            account_name=data["account_name"],
            full_name=data.get("full_name"),
            preferences=data.get("preferences", {}),
            active=data.get("active", True),
        )

    def upsert_user_profile(self, profile: UserProfile) -> None:
        path = self.base_path / "users"
        self._ensure_dir(path)

        data = {
            "account_name": profile.account_name,
            "full_name": profile.full_name,
            "preferences": profile.preferences,
        }

        self._atomic_write(path / f"{profile.account_name}.json", data)

    # ----------------------------------------------------------------------
    # Backwards-compatible aliases (older tests / API)
    # ----------------------------------------------------------------------

    def save_user(self, account_name: str, profile: Dict[str, Any]) -> None:
        """Compatibility wrapper for older tests.

        Expected input shape in tests:
          {"name": "...", "preferences": {...}}
        """
        user_profile = UserProfile(
            account_name=account_name,
            full_name=profile.get("name"),
            preferences=profile.get("preferences", {}),
            active=True,
        )
        self.upsert_user_profile(user_profile)

    def load_user(self, account_name: str) -> Optional[Dict[str, Any]]:
        """Compatibility wrapper for older tests."""
        profile = self.get_user_profile(account_name)
        if not profile:
            return None
        return {
            "name": profile.full_name,
            "preferences": profile.preferences,
        }

    # ----------------------------------------------------------------------
    # AGENT PROFILES
    # ----------------------------------------------------------------------

    def get_agent_profile(self, name: str) -> Optional[AgentProfile]:
        path = self.base_path / "agents" / f"{name}.json"
        data = self._load_json(path)
        if not data:
            return None

        return AgentProfile(
            name=data["name"],
            model=data["model"],
            temperature=data["temperature"],
            message_processor=data["message_processor"],
            config=data.get("config", {}),
        )

    def upsert_agent_profile(self, agent: AgentProfile) -> None:
        path = self.base_path / "agents"
        self._ensure_dir(path)

        data = {
            "name": agent.name,
            "model": agent.model,
            "temperature": agent.temperature,
            "message_processor": agent.message_processor,
            "config": agent.config,
        }

        self._atomic_write(path / f"{agent.name}.json", data)

    # ----------------------------------------------------------------------
    # CONTEXT / WHITEBOARD
    # ----------------------------------------------------------------------

    def get_context(self, account_name: str, context_id: str) -> Optional[ContextState]:
        path = self.base_path / "contexts" / account_name / f"{context_id}.json"
        data = self._load_json(path)
        if not data:
            return None

        return ContextState(
            id=data["id"],
            account_name=data["account_name"],
            data=data["data"],
            updated_at=_parse_dt_utc(data.get("updated_at", "")),
        )

    def save_context(self, context: ContextState) -> None:
        path = self.base_path / "contexts" / context.account_name
        self._ensure_dir(path)

        updated = context.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        else:
            updated = updated.astimezone(timezone.utc)

        data = {
            "id": context.id,
            "account_name": context.account_name,
            "data": context.data,
            "updated_at": updated.isoformat(),
        }

        self._atomic_write(path / f"{context.id}.json", data)

    # ----------------------------------------------------------------------
    # DOCUMENTS
    # ----------------------------------------------------------------------

    def list_documents(
        self,
        account_name: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentRef]:

        doc_dir = self.base_path / "documents" / account_name
        if not doc_dir.exists():
            return []

        docs = []
        for doc_file in doc_dir.glob("*.json"):
            data = self._load_json(doc_file)
            if not data:
                continue

            if kind and data.get("kind") != kind:
                continue
            if tag and tag not in data.get("tags", []):
                continue

            docs.append(self._doc_dict_to_ref(data))

        return docs[:limit]

    def get_document(self, document_id: str) -> Optional[DocumentRef]:
        docs_dir = self.base_path / "documents"
        if not docs_dir.exists():
            return None

        for account_dir in docs_dir.iterdir():
            if not account_dir.is_dir():
                continue

            doc_path = account_dir / f"{document_id}.json"
            if doc_path.exists():
                data = self._load_json(doc_path)
                if data:
                    return self._doc_dict_to_ref(data)

        return None

    def upsert_document(self, doc: DocumentRef) -> None:
        path = self.base_path / "documents" / doc.account_name
        self._ensure_dir(path)

        data = {
            "id": doc.id,
            "account_name": doc.account_name,
            "path": doc.path,
            "kind": doc.kind,
            "title": doc.title,
            "tags": doc.tags,
            "metadata": doc.metadata,
        }

        self._atomic_write(path / f"{doc.id}.json", data)

    def _doc_dict_to_ref(self, data: Dict[str, Any]) -> DocumentRef:
        return DocumentRef(
            id=data["id"],
            account_name=data["account_name"],
            path=data["path"],
            kind=data["kind"],
            title=data.get("title"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    # ----------------------------------------------------------------------
    # SIMPLE DOCUMENT SEARCH ("poor man's embedding")
    # ----------------------------------------------------------------------

    def search_documents_poor_man(
        self,
        account_name: str,
        query: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[DocumentRef]:
        """Simple keyword-based search over documents for an account.

        This is intentionally "quick and dirty": it scores documents based on
        how many times the query terms appear in title, tags, and metadata.
        """

        # Reuse existing listing logic to get candidate docs
        docs = self.list_documents(
            account_name=account_name,
            kind=kind,
            tag=tag,
            limit=1000,  # upper bound of candidates to score
        )

        myKwUtil = Keywords()

        terms = myKwUtil.extract_keywords(query, top_n=10)   

        # Tokenize query into lowercase terms
        # terms = [t for t in query.lower().split() if t.strip()]
        if not terms:
            return docs[:limit]

        scored: List[Tuple[DocumentRef, int]] = []

        for doc in docs:
            # Build a simple text blob from title, tags, and metadata values
            title_text = (doc.title or "").lower()
            tags_text = " ".join(doc.tags).lower()
            metadata_text = " ".join(
                str(v).lower() for v in (doc.metadata or {}).values()
            )

            blob = " ".join([title_text, tags_text, metadata_text])
            blob = myKwUtil.extract_keywords(blob, top_n=50)    

            # Score = sum of term occurrences
            #score = sum(blob.count(term) for term in terms)
            score = len(set(blob) & set(terms))


            if score > 0:
                scored.append((doc, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored[:limit]]

    # ----------------------------------------------------------------------
    # EMBEDDINGS
    # ----------------------------------------------------------------------

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        path = (
            self.base_path
            / "embeddings"
            / record.account_name
            / record.namespace
        )
        self._ensure_dir(path)

        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        else:
            created = created.astimezone(timezone.utc)

        data = {
            "id": record.id,
            "namespace": record.namespace,
            "account_name": record.account_name,
            "vector": record.vector,
            "source_type": record.source_type,
            "source_id": record.source_id,
            "source_metadata": record.source_metadata,
            "created_at": created.isoformat(),
        }

        self._atomic_write(path / f"{record.id}.json", data)

    def query_embeddings(
        self,
        namespace: str,
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:

        path = self.base_path / "embeddings" / account_name / namespace
        if not path.exists():
            return []

        results = []
        for emb_file in path.glob("*.json"):
            data = self._load_json(emb_file)
            if not data:
                continue

            if filter and "source_type" in filter:
                if data.get("source_type") != filter["source_type"]:
                    continue

            vector = data["vector"]
            similarity = self._cosine_similarity(query_vector, vector)

            record = EmbeddingRecord(
                id=data["id"],
                namespace=data["namespace"],
                account_name=data["account_name"],
                vector=vector,
                source_type=data["source_type"],
                source_id=data["source_id"],
                source_metadata=data.get("source_metadata", {}),
                created_at=_parse_dt_utc(data.get("created_at", "")),
            )

            results.append((record, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # ----------------------------------------------------------------------

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        import math

        dot = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    # ----------------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            return self.base_path.exists() and os.access(self.base_path, os.W_OK)
        except Exception:
            return False
