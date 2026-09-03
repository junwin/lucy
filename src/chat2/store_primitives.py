"""
Media-neutral storage primitives for Chat v2.

Defines StoreKey (logical key identifier) and Chat2Primitives
(protocol for any backend: filesystem, SQL, in-memory, etc.).

Also provides InMemoryStore — a dict-backed fake implementation
for testing and development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Union, runtime_checkable


@dataclass(frozen=True)
class StoreKey:
    """A logical storage key, not a filesystem path.

    Rules:
    - Keys are always relative (no leading '/').
    - Keys use '/' as a separator (even on Windows).
    - Keys must not contain '..'.
    - Key construction should be centralized in helper functions.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(f"StoreKey value must be a str, got {type(self.value)}")
        if self.value.startswith("/"):
            raise ValueError(f"StoreKey must be relative (no leading '/'): {self.value}")
        if ".." in self.value.split("/"):
            raise ValueError(f"StoreKey must not contain '..': {self.value}")

    def __str__(self) -> str:
        return self.value


@runtime_checkable
class Chat2Primitives(Protocol):
    """Minimal storage interface that any backend can implement.

    All methods operate on logical StoreKey values, not filesystem paths.

    Document ops (read_text / write_text / append_text / exists / delete)
    manage whole documents; log ops (read_lines / append_lines / truncate)
    manage append-only line streams used for JSONL event logs and the
    correlation index. A key may hold a document and a log at the same
    time (e.g. the empty events.jsonl placeholder plus appended lines).
    """

    def read_text(self, key: StoreKey) -> Optional[str]:
        """Read the full text content at *key*.

        Returns None if the key does not exist.
        """
        ...

    def write_text(self, key: StoreKey, text: str) -> None:
        """Write *text* to *key*, overwriting any existing content.

        Should be atomic if possible.
        """
        ...

    def append_text(self, key: StoreKey, text: str) -> None:
        """Append *text* to the existing content at *key*.

        Required for append-only JSONL event logs.
        """
        ...

    def read_lines(self, key: StoreKey) -> Optional[list[str]]:
        """Return the log lines at *key* in append order, or None if missing.

        Required for append-only JSONL event logs.
        """
        ...

    def append_lines(self, key: StoreKey, lines: Iterable[str]) -> None:
        """Append *lines* to the log at *key*, preserving order.

        An empty batch is a no-op.
        """
        ...

    def truncate(self, key: StoreKey) -> None:
        """Clear the log at *key*, keeping any document at the same key.

        After truncate the log is missing (read_lines -> None) until the
        next append.
        """
        ...

    def exists(self, key: StoreKey) -> bool:
        """Return True if *key* exists in the store."""
        ...

    def delete(self, key: StoreKey) -> None:
        """Remove the content at *key*.

        No-op if the key does not exist.
        """
        ...

    def list_keys(self, prefix: StoreKey) -> list[StoreKey]:
        """Return all keys that start with *prefix*.

        Optional operation; backends that cannot support it may raise
        NotImplementedError.
        """
        ...


class InMemoryStore:
    """A dict-backed implementation of Chat2Primitives for testing.

    Stores documents in a dict[str, str] and log lines in a separate
    dict[str, list[str]] sidecar, mirroring the SQLite backend's
    kv/logs table split.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._logs: dict[str, list[str]] = {}

    @staticmethod
    def _key(key: Union[StoreKey, str]) -> str:
        """Coerce to a validated StoreKey and return its string value."""
        if isinstance(key, str):
            key = StoreKey(key)
        elif not isinstance(key, StoreKey):
            raise TypeError(
                f"key must be StoreKey or str, got {type(key).__name__}"
            )
        return key.value

    def read_text(self, key: Union[StoreKey, str]) -> Optional[str]:
        return self._data.get(self._key(key))

    def write_text(self, key: Union[StoreKey, str], text: str) -> None:
        self._data[self._key(key)] = text

    def append_text(self, key: Union[StoreKey, str], text: str) -> None:
        k = self._key(key)
        existing = self._data.get(k, "")
        self._data[k] = existing + text

    def read_lines(self, key: Union[StoreKey, str]) -> Optional[list[str]]:
        lines = self._logs.get(self._key(key))
        return list(lines) if lines is not None else None

    def append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None:
        items = list(lines)
        if not items:
            return
        self._logs.setdefault(self._key(key), []).extend(items)

    def truncate(self, key: Union[StoreKey, str]) -> None:
        self._logs.pop(self._key(key), None)

    def exists(self, key: Union[StoreKey, str]) -> bool:
        k = self._key(key)
        return k in self._data or k in self._logs

    def delete(self, key: Union[StoreKey, str]) -> None:
        k = self._key(key)
        self._data.pop(k, None)
        self._logs.pop(k, None)

    def list_keys(self, prefix: Union[StoreKey, str]) -> list[StoreKey]:
        p = self._key(prefix)
        keys = {k for k in self._data if k.startswith(p)}
        keys |= {k for k in self._logs if k.startswith(p)}
        return sorted((StoreKey(k) for k in keys), key=lambda k: k.value)


__all__ = ["StoreKey", "Chat2Primitives", "InMemoryStore"]
