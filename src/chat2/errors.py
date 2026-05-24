"""
Exception classes for Chat v2 operations.

All chat2-specific exceptions inherit from Chat2Error, which inherits
from the built-in Exception class.
"""


class Chat2Error(Exception):
    """Base exception for all chat2 module errors."""


class SessionNotFoundError(Chat2Error):
    """Raised when a session operation targets a non-existent session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class EventNotFoundError(Chat2Error):
    """Raised when a specific event cannot be found."""

    def __init__(self, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(f"Event not found: {event_id}")


class CorruptEventLogError(Chat2Error):
    """Raised when an event log contains unparseable data."""

    def __init__(self, session_id: str, line_number: int, detail: str = "") -> None:
        self.session_id = session_id
        self.line_number = line_number
        self.detail = detail
        msg = f"Corrupt event log in session {session_id} at line {line_number}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class CorruptMetaError(Chat2Error):
    """Raised when session metadata cannot be parsed."""

    def __init__(self, session_id: str, detail: str = "") -> None:
        self.session_id = session_id
        self.detail = detail
        msg = f"Corrupt session metadata for session {session_id}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class StorageOperationError(Chat2Error):
    """Raised when a storage backend operation fails unexpectedly."""

    def __init__(self, operation: str, key: str, detail: str = "") -> None:
        self.operation = operation
        self.key = key
        self.detail = detail
        msg = f"Storage operation '{operation}' failed for key '{key}'"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


__all__ = [
    "Chat2Error",
    "SessionNotFoundError",
    "EventNotFoundError",
    "CorruptEventLogError",
    "CorruptMetaError",
    "StorageOperationError",
]
