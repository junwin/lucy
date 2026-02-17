# ==============================================================================
# FILE: src/storage/json_file_storage.py
# JSON-backed storage implementation for Lucy.
# NOTE: contexts are now persisted as Markdown (.md) with YAML frontmatter.
# ==============================================================================

import json
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.keywords.keywords import Keywords
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.task_list import TaskList, Task  
from src.tasklists.service import TaskListService


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

import yaml
import re

from src.storage.json_file_storage_parts import chats 


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
    """JSON-backed storage implementation for Lucy.

    Notes:
      - Per-account chat metadata includes an index file at <chats>/<account>/index.json
        which maps session_id -> metadata. The index schema produced by
        create_chat_session() is:

        {
          "<session_id>": {
              "friendly_name": "...",
              "agent_name": "...",
              "account_name": "...",
              "updated_at": "2023-...",
              "include_in_context": true
          },
          ...
        }

      - Contexts were previously stored as JSON files under
        contexts/<account>/<context_id>.json. They are now stored as
        Markdown files (<context_id>.md) with YAML frontmatter. Frontmatter
        keys map into ContextState.data (excluding 'text'); the Markdown body
        is stored in data['text']. The ContextState.updated_at timestamp is
        taken from the frontmatter 'updated_at' if present, otherwise from
        the file's mtime.
    """

    def __init__(self, storage_paths: StoragePaths):

        self.storage_paths = storage_paths
        self._tasklist_service = TaskListService()


    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON atomically."""
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """Write text (e.g. Markdown) atomically."""
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
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
        return chats.create_chat_session(self, account_name=account_name, agent_name=agent_name, friendly_name=friendly_name, tags=tags)


    def find_chat_sessions_by_friendly_name(self, account_name: str, agent_name: str, friendly_name: str, limit: int = 20) -> List[ChatSession]:
        return chats.find_chat_sessions_by_friendly_name(self, account_name, agent_name, friendly_name, limit)

    # ----------------------------------------------------------------------

    def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        return chats.get_chat_session(self, session_id)

    # ----------------------------------------------------------------------    # ----------------------------------------------------------------------

    def list_chat_sessions(
        self,
        account_name: str,
        agent_name: Optional[str] = None,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[ChatSession]:
        return chats.list_chat_sessions(
            self,
            account_name=account_name,
            agent_name=agent_name,
            limit=limit,
            before=before,
        )

    # ----------------------------------------------------------------------

    def rename_chat_session(self, session_id: str, friendly_name: str) -> None:
        """Backward-compatible API — delegates to update_chat_session()"""
        return chats.rename_chat_session(self, session_id, friendly_name)

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

        return chats.update_chat_session(
            self,
            session_id,
            friendly_name=friendly_name,
            tags=tags,
            summary=summary,
            importance_score=importance_score,
            include_in_context=include_in_context,
            metadata=metadata,
        )

    # ----------------------------------------------------------------------

    def append_chat_message(self, session_id: str, message: ChatMessage) -> None:
        return chats.append_chat_message(self, session_id, message)

    # ----------------------------------------------------------------------

    def delete_chat_session(self, session_id: str) -> None:
        return chats.delete_chat_session(self, session_id)

    def _chat_dict_to_session(self, data: Dict[str, Any]) -> ChatSession:
        """Convert stored JSON dict → ChatSession dataclass."""

        return chats._chat_dict_to_session(self, data)

    # ----------------------------------------------------------------------
    # USER PROFILES
    # ----------------------------------------------------------------------

    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        path = self.storage_paths.users / f"{account_name}.json"
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
        path = self.storage_paths.users
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
        path = self.storage_paths.agents / f"{name}.json"
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
        path = self.storage_paths.agents
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
        """Load a context from Markdown (.md) with YAML frontmatter.

        Frontmatter keys map into ContextState.data (excluding 'text'), and the
        Markdown body is stored as data['text']. The ContextState.updated_at is
        sourced from frontmatter['updated_at'] if present; otherwise the file's
        modification time is used.
        """
        path = self.storage_paths.contexts / account_name / f"{context_id}.md"
        if not path.exists():
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logging.error("Failed to read context file %s: %s", path, e)
            return None

        fm = {}
        body = ""
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
        if m:
            fm_text = m.group(1)
            body = m.group(2)
            try:
                loaded = yaml.safe_load(fm_text)
                if isinstance(loaded, dict):
                    fm = loaded
                else:
                    fm = {}
            except Exception as e:
                logging.warning("Failed to parse YAML frontmatter for %s: %s", path, e)
                fm = {}
        else:
            # No frontmatter; treat whole file as body
            body = text

        # Map frontmatter keys into context.data (excluding 'text'), and body into 'text'
        data: Dict[str, Any] = {}
        for k, v in (fm or {}).items():
            data[k] = v

        data["text"] = body

        # Determine updated_at: prefer frontmatter 'updated_at' if present; else mtime
        updated_at = None
        if "updated_at" in fm:
            try:
                updated_at = _parse_dt_utc(fm.get("updated_at") or "")
            except Exception:
                updated_at = None

        if updated_at is None:
            try:
                mtime = path.stat().st_mtime
                updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
            except Exception:
                updated_at = _now_utc()

        return ContextState(
            id=context_id,
            account_name=account_name,
            data=data,
            updated_at=updated_at,
        )

    def get_or_create_context(
        self,
        account_name: str,
        context_id: str,
        *,
        default_data: Optional[Dict[str, Any]] = None,
    ) -> ContextState:
        """Load a context; if missing, create and save it immediately.

        When creating a new context, default_data is merged onto default fields.
        """
        existing = self.get_context(account_name=account_name, context_id=context_id)
        if existing is not None:
            return existing

        data: Dict[str, Any] = {
            "context_name": context_id,
            "agreed": False,
            "tasklist_status": "draft",
            "text": "",
        }
        if default_data:
            # Allow caller to override/extend defaults
            data.update(default_data)

        ctx = ContextState(
            id=context_id,
            account_name=account_name,
            data=data,
            updated_at=_now_utc(),
        )
        self.save_context(ctx)
        return ctx

    def save_context(self, context: ContextState) -> None:
        """Persist a ContextState as Markdown (.md) with YAML frontmatter.

        Frontmatter contains all keys from context.data except 'text'. The
        Markdown body contains context.data.get('text', ''). The file's
        modification time is set to context.updated_at (UTC) to preserve the
        timestamp.
        """
        path = self.storage_paths.contexts / context.account_name
        self._ensure_dir(path)

        updated = context.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        else:
            updated = updated.astimezone(timezone.utc)

        # Frontmatter: all keys from context.data except 'text'
        fm: Dict[str, Any] = {}
        for k, v in context.data.items():
            if k == "text":
                continue
            # Ensure that tasklist remains a plain dict when present
            fm[k] = v

        try:
            fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        except Exception:
            # Fallback: ensure YAML serialization doesn't crash
            fm_yaml = yaml.safe_dump({}, sort_keys=False, allow_unicode=True)

        body = context.data.get("text", "") or ""

        # Compose Markdown with YAML frontmatter
        content = f"---\n{fm_yaml}---\n{body}"

        target = path / f"{context.id}.md"
        # Write atomically
        self._atomic_write_text(target, content)

        # Preserve updated_at via file mtime so get_context can read it when needed
        try:
            ts = updated.timestamp()
            os.utime(target, (ts, ts))
        except Exception:
            # Not critical; file will just have current mtime
            pass

    def list_context_names(self, account_name: str) -> List[str]:
        """List context names (filename stems) for an account in sorted order.

        Only .md files are considered.
        """
        ctx_dir = self.storage_paths.contexts / account_name
        if not ctx_dir.exists() or not ctx_dir.is_dir():
            return []

        names: List[str] = []
        for p in ctx_dir.glob("*.md"):
            # filename stem without suffix
            names.append(p.stem)

        names.sort()
        return names

    def migrate_context_json_to_md(self) -> None:
        """Migration helper: convert existing contexts/*.json → *.md.

        This will iterate accounts and for each <id>.json file create a
        corresponding <id>.md file if one does not already exist. It preserves
        the original 'data' dict and the updated_at timestamp (if present) by
        setting the md file mtime.
        """
        base = self.storage_paths.contexts
        if not base.exists():
            return

        for account_dir in base.iterdir():
            if not account_dir.is_dir():
                continue
            for json_file in account_dir.glob("*.json"):
                try:
                    data = self._load_json(json_file)
                    if not data:
                        continue
                    ctx_id = data.get("id") or json_file.stem
                    md_path = account_dir / f"{ctx_id}.md"
                    if md_path.exists():
                        # Skip if md already present
                        continue

                    ctx_data = data.get("data", {})
                    # Ensure text key exists
                    if "text" not in ctx_data:
                        ctx_data["text"] = ""

                    updated_at = None
                    if data.get("updated_at"):
                        try:
                            updated_at = _parse_dt_utc(data.get("updated_at"))
                        except Exception:
                            updated_at = None

                    ctx = ContextState(
                        id=ctx_id,
                        account_name=account_dir.name,
                        data=ctx_data,
                        updated_at=updated_at or _now_utc(),
                    )

                    # Use save_context to write md
                    self.save_context(ctx)
                except Exception as e:
                    logging.error("Failed migrating %s: %s", json_file, e)

    # ----------------------------------------------------------------------
    # Tasklists (simple CRUD)
    # ----------------------------------------------------------------------

    def _tasklists_dir(self, account_name: str) -> Path:
        # store tasklist templates under documents/<account>/tasklists/
        d = self.storage_paths.tasklists / account_name
        return d

    def _tasklist_path(self, account_name: str, tasklist_id: str) -> Path:
        """Return a resolved, safe Path for a tasklist JSON file using StoragePaths.resolve_relative.

        This ensures user-supplied account names or ids cannot escape the
        storage namespace.
        """
        # Build a relative path under base and resolve via storage_paths
        rel = f"tasklists/{account_name}/{tasklist_id}.json"
        return self.storage_paths.resolve_relative(rel)

    def list_tasklists(self, account_name: str) -> List[str]:
        d = self._tasklists_dir(account_name)
        if not d.exists() or not d.is_dir():
            return []

        ids: List[str] = []
        for p in d.glob("*.json"):
            ids.append(p.stem)

        ids.sort()
        return ids

    def get_tasklist(self, account_name: str, tasklist_id: str) -> Optional[TaskList]:
        """Load a tasklist from storage using TaskListService."""

        path = self._tasklist_path(account_name, tasklist_id)
        try:
            return self._tasklist_service.load(str(path))
        except FileNotFoundError:
            return None

    def save_tasklist(self, account_name: str, tasklist_name: str, tasklist: TaskList) -> None:
        """Save a tasklist to storage using TaskListService."""

        # Basic id validation: only allow simple filenames (alnum, dash, underscore)
        import re as _re

        if not tasklist_name or not _re.match(r"^[A-Za-z0-9_-]+$", tasklist_name):
            raise ValueError(f"Invalid tasklist name: {tasklist_name!r}")

        tl = TaskList.from_dict(tasklist) if isinstance(tasklist, dict) else tasklist

        path = self._tasklist_path(account_name, tasklist_name)
        self._ensure_dir(path.parent)
        self._tasklist_service.save(str(path), tl)

    def delete_tasklist(self, account_name: str, tasklist_id: str) -> None:

        path = self._tasklist_path(account_name, tasklist_id)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logging.error("Failed to delete tasklist %s: %s", path, e)

    # ----------------------------------------------------------------------
    # DOCUMENTS
    # ----------------------------------------------------------------------

    def list_documents(
        self,
        account_name: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        select_limit: int = 100,
    ) -> List[DocumentRef]:

        logging.debug("list_documents called: account=%s kind=%s tag=%r select_limit=%s", account_name, kind, tag, select_limit)

        doc_dir = self.storage_paths.documents / account_name
        if not doc_dir.exists():
            return []

        docs = []
        for doc_file in doc_dir.glob("*.json"):
            data = self._load_json(doc_file)
            if not data:
                continue

            if kind and data.get("kind") != kind:
                continue
            # If tag is provided (could be empty string), strictly require it to be present
            if tag is not None and tag not in data.get("tags", []):
                continue

            docs.append(self._doc_dict_to_ref(data))

        return docs[:select_limit]

    def get_document(self, document_id: str) -> Optional[DocumentRef]:
        docs_dir = self.storage_paths.documents
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
        path = self.storage_paths.documents / doc.account_name
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
            select_limit=100,  # upper bound of candidates to score
        )

        myKwUtil = Keywords()

        terms = myKwUtil.extract_keywords(query, top_n=20)   

        # Tokenize query into lowercase terms
        # terms = [t for t in query.lower().split() if t.strip()]
        if not terms:
            return []

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
            self.storage_paths.base
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

        path = self.storage_paths.base / "embeddings" / account_name / namespace
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
            return self.storage_paths.base.exists() and os.access(self.storage_paths.base, os.W_OK)
        except Exception:
            return False
