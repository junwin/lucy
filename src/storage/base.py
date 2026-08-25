# src/storage/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from .interfaces import (
    ContextStore,
    DocumentStore,
    EmbeddingStore,
    HealthCheckable,
    TasklistStore,
)
from .models import UserProfile


class Storage(
    ContextStore,
    TasklistStore,
    DocumentStore,
    EmbeddingStore,
    HealthCheckable,
    ABC,
):
    """Abstract storage interface for Lucy."""

    @abstractmethod
    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        """Return stored user profile if it exists."""
        pass
