from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.tasklists import TaskList
from src.topics.schemas import TopicEvent, TopicRecord

from .models import Context, DocumentRef, EmbeddingRecord, Skill


class ContextStore(ABC):
    @abstractmethod
    def get_context(self, account_name: str, context_id: str) -> Optional[Context]:
        """Load a context, resolve imports, and return a fully-resolved Context."""
        pass

    @abstractmethod
    def get_or_create_context(
        self,
        account_name: str,
        context_id: str,
    ) -> Context:
        """Fetch a context, creating + saving it if missing."""
        pass

    @abstractmethod
    def save_context(self, context: Context) -> None:
        """Insert or update a context (persisted fields only; derived fields ignored)."""
        pass

    def list_context_names(self, account_name: str) -> List[str]:
        """List context names for an account.

        Minimal contract:
        - Return the filename stem for each "*.json" file under
          "contexts/<account_name>/" in storage.
        - Return an empty list if the account has no contexts or does not exist.
        - Results should be stable and deterministic (implementations should
          sort by name ascending).

        This is intentionally non-abstract for backward compatibility with
        older/custom Storage implementations.
        """

        return []

    def get_skill(self, account_name: str, skill_name: str) -> Optional[Skill]:
        """Return a skill (frontmatter + body), or None if missing.

        Skills are stored as Markdown files at skills/<account>/<name>.md.
        This is non-abstract so custom Storage implementations can opt in
        without breaking (default: no skills).
        """
        return None

    def get_skill_text(self, account_name: str, skill_name: str) -> Optional[str]:
        """Return the body text of a skill file, or None if missing.

        Backward-compat wrapper: delegates to get_skill().text so custom
        Storage implementations only need to implement get_skill().
        """
        skill = self.get_skill(account_name, skill_name)
        if skill is None:
            return None
        return skill.text


class TasklistStore(ABC):
    @abstractmethod
    def list_tasklists(self, account_name: str) -> List[str]:
        """Return a list of persisted tasklist ids for an account.

        Minimal contract: return an empty list when none exist. Results should
        be stable and deterministic (sorted ascending).
        """
        pass

    @abstractmethod
    def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        """Return a persisted tasklist (plain dict) or None if missing."""
        pass

    @abstractmethod
    def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        """Persist a tasklist model (dict or JSON string) for the account."""
        pass

    @abstractmethod
    def delete_tasklist(self, account_name: str, tasklist_key: str) -> None:
        """Delete a persisted tasklist. Must be idempotent: no error if missing."""
        pass


class DocumentStore(ABC):
    @abstractmethod
    def list_documents(
        self,
        account_name: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        select_limit: int = 100,
    ) -> List[DocumentRef]:
        """List known documents for an account."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[DocumentRef]:
        """Get a document reference by id."""
        pass

    @abstractmethod
    def upsert_document(self, doc: DocumentRef) -> None:
        """Create or update a document reference."""
        pass


class EmbeddingStore(ABC):
    @abstractmethod
    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        """Insert or update an embedding vector record."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def delete_embeddings(
        self,
        namespace: str,
        account_name: str,
        *,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> int:
        """Delete embedding records matching the given filters.

        Filters are ANDed; passing none deletes every record in the
        namespace/account scope. ``record_id`` targets one exact record id
        within that scope and never expands to other records sharing the
        same source_id. Returns count of deleted records. Idempotent:
        returns 0 if no matching records exist.
        """
        pass

    @abstractmethod
    def list_embeddings(
        self,
        namespace: str,
        account_name: str,
    ) -> List[EmbeddingRecord]:
        """Return every embedding record in a namespace for an account.

        Deterministic order: sorted by record id ascending. Returns an
        empty list when the namespace/account has no records.
        """
        pass

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        """List available embedding namespaces for an account.

        Returns subdirectory names under embeddings/<account_name>/.
        This is non-abstract for backward compatibility with custom Storage
        implementations. Returns empty list if the account has no embeddings.
        """
        return []


class EventStore(ABC):
    """Append-only event log seam for topic streams (issue #129).

    Integration point for the topics component (decision 4): implemented by
    ``src/topics/streams.py``, consumed by the FCP once integrated. Streams
    are partitioned by **topic** (inbox + one per explicit topic), never by
    agent (decision 7) - any agent can append to any stream.

    The log is append-only: events are never updated or deleted (corrections
    are new events). ``stream`` is physical placement at write time, not topic
    membership (decision 1); membership is derived by the index.
    """

    @abstractmethod
    def append_event(self, account: str, stream: str, event: TopicEvent) -> TopicEvent:
        """Append an event to a stream.

        Raises if the stream does not exist (e.g. archived topics reject new
        writes). Returns the event as persisted.
        """
        pass

    @abstractmethod
    def stream_events(self, account: str, stream: str) -> Iterator[TopicEvent]:
        """Yield events from a stream in append order (oldest first)."""
        pass

    @abstractmethod
    def read_events(
        self,
        account: str,
        stream: str,
        *,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[TopicEvent]:
        """Read events from a stream with optional time bounds and a cap."""
        pass


class TopicStore(ABC):
    """Topic lifecycle + query seam (issue #129).

    Integration point for the topics component (decision 4): implemented by
    ``src/topics/mutation.py`` (mutations) and ``src/topics/queries.py``
    (queries), consumed by the FCP once integrated.

    Every mutation appends events to the log; nothing is ever mutated in
    place. Identity model (pinned 2026-09-01): ``topic_id`` = immutable slug;
    ``name`` = mutable label; rename changes the name only.
    """

    @abstractmethod
    def create_topic(
        self,
        account: str,
        name: str,
        slug_proposal: str,
        *,
        agent: str,
        description: Optional[str] = None,
    ) -> str:
        """Create an explicit topic; returns the resolved stored slug."""
        pass

    @abstractmethod
    def rename_topic(
        self,
        account: str,
        slug: str,
        new_name: str,
        *,
        agent: str,
    ) -> None:
        """Rename a topic (name only; the slug never changes)."""
        pass

    @abstractmethod
    def link_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        """Re-tag event ids into a topic (membership changes; events never move)."""
        pass

    @abstractmethod
    def unlink_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
    ) -> None:
        """Remove event ids from a topic (append-only re-tagging)."""
        pass

    @abstractmethod
    def merge_topics(
        self,
        account: str,
        source: str,
        target: str,
        *,
        agent: str,
    ) -> None:
        """Merge source into target: source frozen, its event ids re-linked."""
        pass

    @abstractmethod
    def archive_topic(
        self,
        account: str,
        slug: str,
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        """Archive a topic (event + freeze only in v1; no physical copy)."""
        pass

    @abstractmethod
    def get_topic(self, account: str, slug: str) -> Optional[TopicRecord]:
        """Return a topic record (projection) by slug, or None if missing."""
        pass

    @abstractmethod
    def list_topics(
        self,
        account: str,
        *,
        kind: Optional[str] = None,
    ) -> List[TopicRecord]:
        """List topic records, optionally filtered by kind
        (``explicit``, ``temporal``, ``inferred``)."""
        pass


class HealthCheckable(ABC):
    @abstractmethod
    def health_check(self) -> bool:
        """Quick check that storage is reachable."""
        pass
