"""
Chat v2 storage module.

This module provides a new chat storage system with:
- Media-neutral storage primitives
- Multi-agent support
- Append-only JSONL event logs
- Backward compatibility with existing JsonFileStorage
"""

from src.chat2.errors import (
    Chat2Error,
    CorruptEventLogError,
    CorruptMetaError,
    EventNotFoundError,
    SessionNotFoundError,
    StorageOperationError,
)
from src.chat2.facade import Chat2Store

__version__ = "0.1.0"

__all__ = [
    "Chat2Error",
    "Chat2Store",
    "CorruptEventLogError",
    "CorruptMetaError",
    "EventNotFoundError",
    "SessionNotFoundError",
    "StorageOperationError",
]
