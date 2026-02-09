# src/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList

from .models import (
    ChatMessage,
    ChatSession,
    UserProfile,
    AgentProfile,
    ContextState,
    DocumentRef,
    EmbeddingRecord,
)


class Storage(ABC):
    """Abstract storage interface for Lucy."""

    @abstractmethod
    def create_chat_session(
        self,
        account_name: str,
        agent_name: str,
        friendly_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> ChatSession:
        """Create a new chat session and return it."""
        pass

    @abstractmethod
    def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        """Return a full chat session (including messages), or None."""
        pass

    @abstractmethod
    def list_chat_sessions(
        self,
        account_name: str,
        agent_name: Optional[str] = None,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[ChatSession]:
        """List recent chat sessions for a user."""
        pass

    @abstractmethod
    def rename_chat_session(self, session_id: str, friendly_name: str) -> None:
        """Update the human-friendly name for a session."""
        pass

    @abstractmethod
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
        """Update chat session metadata."""
        pass

    @abstractmethod
    def append_chat_message(
        self,
        session_id: str,
        message: ChatMessage,
    ) -> None:
        """Append a message to a session."""
        pass

    @abstractmethod
    def delete_chat_session(self, session_id: str) -> None:
        """Delete a chat session and all its messages.

        Should be idempotent: deleting a non-existent session is allowed
        and should not raise, unless the implementation wants to signal
        that explicitly.
        """
        pass

    @abstractmethod
    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        """Return stored user profile if it exists."""
        pass

    @abstractmethod
    def upsert_user_profile(self, profile: UserProfile) -> None:
        """Create or update user profile."""
        pass

    @abstractmethod
    def get_agent_profile(self, name: str) -> Optional[AgentProfile]:
        """Return agent profile."""
        pass

    @abstractmethod
    def upsert_agent_profile(self, agent: AgentProfile) -> None:
        """Create or update agent profile."""
        pass

    @abstractmethod
    def get_context(self, account_name: str, context_id: str) -> Optional[ContextState]:
        """Fetch the context state."""
        pass

    @abstractmethod
    def get_or_create_context(
        self,
        account_name: str,
        context_id: str,
    ) -> ContextState:
        """Fetch the context state, creating it if it does not exist."""
        pass

    @abstractmethod
    def save_context(self, context: ContextState) -> None:
        """Insert or update a context state."""
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

    @abstractmethod
    def list_tasklists(self, account_name: str) -> List[str]:
        """Return a list of persisted tasklist ids for an account.

        Minimal contract: return an empty list when none exist. Results should
        be stable and deterministic (sorted ascending).
        """
        pass

    @abstractmethod
    def get_tasklist(self, account_name: str, tasklist_id: str) -> Optional[TaskList]:
        """Return a persisted tasklist (plain dict) or None if missing."""
        pass

    @abstractmethod
    def save_tasklist(self, account_name: str, tasklist_id: str, tasklist: TaskList) -> None:
        """Persist a tasklist model (dict or JSON string) for the account."""
        pass

    @abstractmethod
    def delete_tasklist(self, account_name: str, tasklist_id: str) -> None:
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
        namespace: str,
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:
        """Vector search: return [(EmbeddingRecord, score), ...]."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Quick check that storage is reachable."""
        pass
