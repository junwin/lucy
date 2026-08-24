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
    UserProfile,
    DocumentRef,
    EmbeddingRecord,
)
from .json_file_storage_parts.contexts import ContextsMixin


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


class JsonFileStorage(ContextsMixin, Storage):
    """JSON-backed storage implementation for Lucy.

    Notes:
      - Contexts were previously stored as JSON files under
        contexts/<account>/<context_id>.json. They are now stored as
        Markdown files (<context_id>.md) with YAML frontmatter. Frontmatter
        keys map onto the persisted Context fields (tag, imports,
        mandatory_tools, search_namespaces, updated_at); unknown keys land
        in Context.extra. The Markdown body is stored in Context.text. The
        Context.updated_at timestamp is taken from the frontmatter
        'updated_at' if present, otherwise from the file's mtime.
    """

    def __init__(self, storage_paths: StoragePaths):

        self.storage_paths = storage_paths
        self._tasklist_service = TaskListService()


    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON atomically.

        Writes to a unique tmp file (uuid4().hex) colocated with the target,
        then atomically replaces the target via os.replace. Unique tmp names
        ensure concurrent writers never collide on a shared tmp path, and
        os.replace is atomic on both Windows and POSIX.
        """
        tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._atomic_replace(tmp_path, path)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """Write text (e.g. Markdown) atomically.

        Same unique-tmp + os.replace strategy as _atomic_write.
        """
        tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        self._atomic_replace(tmp_path, path)

    def _atomic_replace(self, tmp_path: Path, target_path: Path) -> None:
        """Atomically replace target_path with tmp_path.

        Uses os.replace(), which atomically replaces an existing destination on
        both Windows and POSIX. shutil.move() is NOT safe here: on Windows it
        silently falls back to copy2+unlink when the destination exists, which
        is not atomic and can leave a truncated/partial file. tmp is always
        colocated with the target, so a cross-device fallback is unnecessary;
        if one is ever added it must also use unique tmp names.
        """
        try:
            os.replace(tmp_path, target_path)
        except Exception as e:
            logging.error(
                "Atomic replace failed for %s → %s: %s",
                tmp_path, target_path, e,
            )
            try:
                tmp_path.unlink()
            except Exception:
                pass
            raise

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

    def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        """Load a tasklist from storage using TaskListService."""

        path = self._tasklist_path(account_name, tasklist_key)
        try:
            return self._tasklist_service.load(str(path))
        except FileNotFoundError:
            return None

    def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        """Save a tasklist to storage using TaskListService."""

        # Basic id validation: only allow simple filenames (alnum, dash, underscore)
        import re as _re

        if not tasklist_key or not _re.match(r"^[A-Za-z0-9_-]+$", tasklist_key):
            raise ValueError(f"Invalid tasklist key: {tasklist_key!r}")

        tl = TaskList.from_dict(tasklist) if isinstance(tasklist, dict) else tasklist

        # Enforce key == id: the tasklist id must match its storage key
        if tl.id != tasklist_key:
            tl.id = str(tasklist_key)


        path = self._tasklist_path(account_name, tasklist_key)
        self._ensure_dir(path.parent)
        self._tasklist_service.save(str(path), tl)

    def delete_tasklist(self, account_name: str, tasklist_key: str) -> None:

        path = self._tasklist_path(account_name, tasklist_key)
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

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        """List available embedding namespaces for an account.

        Returns subdirectory names under embeddings/<account_name>/,
        sorted alphabetically. Returns empty list if the account has
        no embeddings.
        """
        emb_dir = self.storage_paths.base / "embeddings" / account_name
        if not emb_dir.exists() or not emb_dir.is_dir():
            return []

        namespaces: List[str] = []
        for p in emb_dir.iterdir():
            if p.is_dir():
                namespaces.append(p.name)

        namespaces.sort()
        return namespaces

    def delete_embeddings(
        self,
        namespace: str,
        account_name: str,
        *,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> int:
        """Delete embedding records matching the given filters.

        Returns count of deleted records. Idempotent: returns 0 if no
        matching records exist.
        """
        path = self.storage_paths.base / "embeddings" / account_name / namespace
        if not path.exists():
            return 0

        deleted = 0
        for emb_file in path.glob("*.json"):
            data = self._load_json(emb_file)
            if not data:
                continue
            if source_id is not None and data.get("source_id") != source_id:
                continue
            if source_type is not None and data.get("source_type") != source_type:
                continue
            try:
                emb_file.unlink()
                deleted += 1
            except Exception as e:
                logging.error("Failed to delete embedding file %s: %s", emb_file, e)

        return deleted

    def query_embeddings(
        self,
        namespaces: List[str],
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:
        """Vector search across one or more namespaces.

        Queries each namespace, merges all results, sorts by score descending,
        and returns the top_k across all namespaces combined.
        """
        results: List[Tuple[EmbeddingRecord, float]] = []

        for namespace in namespaces:
            path = self.storage_paths.base / "embeddings" / account_name / namespace
            if not path.exists():
                continue

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
