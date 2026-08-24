# src/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

# Use the tasklists compatibility layer which exposes the appropriate
# Task/TaskList types (legacy dataclasses or Pydantic models) so storage
# implementations don't have to import from deep paths.
from src.tasklists import Task, TaskList

from .models import (
    UserProfile,
    Context,
    Skill,
    DocumentRef,
    EmbeddingRecord,
)


class Storage(ABC):
    """Abstract storage interface for Lucy."""

    @abstractmethod
    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        """Return stored user profile if it exists."""
        pass

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
    ) -> int:
        """Delete embedding records matching the given filters.

        Returns count of deleted records. Idempotent: returns 0 if no
        matching records exist.
        """
        pass

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        """List available embedding namespaces for an account.

        Returns subdirectory names under embeddings/<account_name>/.
        This is non-abstract for backward compatibility with custom Storage
        implementations. Returns empty list if the account has no embeddings.
        """
        return []

    @abstractmethod
    def health_check(self) -> bool:
        """Quick check that storage is reachable."""
        pass
