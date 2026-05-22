"""
Media-neutral storage primitives for Chat v2.

Defines StoreKey (logical key identifier) and Chat2Primitives
(protocol for any backend: filesystem, SQL, in-memory, etc.).

Also provides InMemoryStore — a dict-backed fake implementation
for testing and development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


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

    Stores all data in memory as a dict[str, str]. Useful for unit tests
    and development without filesystem dependencies.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def read_text(self, key: StoreKey) -> Optional[str]:
        return self._data.get(key.value)

    def write_text(self, key: StoreKey, text: str) -> None:
        self._data[key.value] = text

    def append_text(self, key: StoreKey, text: str) -> None:
        existing = self._data.get(key.value, "")
        self._data[key.value] = existing + text

    def exists(self, key: StoreKey) -> bool:
        return key.value in self._data

    def delete(self, key: StoreKey) -> None:
        self._data.pop(key.value, None)

    def list_keys(self, prefix: StoreKey) -> list[StoreKey]:
        return [StoreKey(k) for k in self._data if k.startswith(prefix.value)]


__all__ = ["StoreKey", "Chat2Primitives", "InMemoryStore"]
