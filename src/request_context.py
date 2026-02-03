"""Request-scoped context utilities.

This module provides small helpers for storing and retrieving request-scoped
values using :mod:`contextvars`.

Currently supported context values:
- request_id: short-lived correlation id for the active HTTP request
- account_name: optional account identifier for the active request

The request_id is set at request start (see app.py) and can be used
anywhere in-process. Logging is configured with a Filter that injects
request_id into every LogRecord.
"""

from __future__ import annotations

import contextvars
from contextlib import AbstractContextManager
from typing import Optional

# Public context variables --------------------------------------------------

# Request id used for log correlation. Default is '-' which matches the
# existing logging configuration used across the project.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# Optional account name for the active request. Some handlers may set this so
# downstream code can access the current account without threading it through
# call signatures.
account_name_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "account_name", default=None
)


# Convenience helpers ------------------------------------------------------

def get_request_id() -> str:
    """Return the current request id (never None)."""

    return request_id_var.get("-")


def set_request_id(rid: str) -> contextvars.Token:
    """Set the request id for the current context and return the token.

    The caller may later call ``request_id_var.reset(token)`` to restore the
    previous value.
    """

    return request_id_var.set(rid)


def get_account_name() -> Optional[str]:
    """Return the current account name or ``None`` if not set."""

    return account_name_var.get(None)


def set_account_name(account_name: Optional[str]) -> contextvars.Token:
    """Set the account name for the current context and return the token."""

    return account_name_var.set(account_name)


class request_context(AbstractContextManager):
    """Context manager for temporarily setting request-scoped values.

    Example:
        with request_context(request_id="abc", account_name="alice"):
            ...
    """

    def __init__(self, request_id: Optional[str] = None, account_name: Optional[str] = None) -> None:
        self._request_id = request_id
        self._account_name = account_name
        self._tokens: list[contextvars.Token] = []

    def __enter__(self) -> "request_context":
        if self._request_id is not None:
            self._tokens.append(set_request_id(self._request_id))
        if self._account_name is not None:
            self._tokens.append(set_account_name(self._account_name))
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        # restore in reverse order
        while self._tokens:
            token = self._tokens.pop()
            token.var.reset(token)
        return False


# Backwards compatible single-name export used by app.py
__all__ = [
    "request_id_var",
    "account_name_var",
    "get_request_id",
    "set_request_id",
    "get_account_name",
    "set_account_name",
    "request_context",
]
