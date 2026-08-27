# src/storage/__init__.py
"""
Lucy's storage layer.

Provides a unified interface for storing and retrieving:
- Contexts (shared state)
- Documents and embeddings

Usage:
    from src.storage import JsonFileStorage, UserProfile
"""

# Base interface
from .base import Storage

# Implementations
from .json_file_storage import JsonFileStorage

# Data models
from .models import (
    UserProfile,
    Context,
    Skill,
    DocumentRef,
    EmbeddingRecord,
)


__all__ = [
    "Storage",
    "JsonFileStorage",
    "UserProfile",
    "Context",
    "Skill",
    "DocumentRef",
    "EmbeddingRecord",
]
