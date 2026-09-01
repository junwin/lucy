"""
SQLite backend for the generic-store doc/log protocol (chat2 primitives).

Implements SqliteChat2Primitives on top of the schema in schema.sql.
Two tables, one per data shape:

  kv   -> documents (read_text / write_text / exists / delete)
  logs -> append-only line streams (read_lines / append_lines / truncate)

Design notes
------------
- One connection, WAL journal mode (set in schema.sql and re-applied on
  the connection so in-memory test databases behave the same way).
- All StoreKey validation is reused from store_primitives.StoreKey.
- ``read_lines`` returns None when the key has no log rows (missing log).
  After ``truncate`` the log is missing until the next append.
- ``truncate`` only clears the log table. A document stored at the same
  key (e.g. the empty ``events.jsonl`` doc written by ``create_session``)
  is kept, which is what "truncate keeps key" means.
- ``delete`` removes the key from both tables.
- ``list_keys`` unions keys from both tables and matches the prefix with
  LIKE + ESCAPE, so '%' and '_' inside the prefix match literally. LIKE
  is made case-sensitive via PRAGMA case_sensitive_like, matching StoreKey
  (and InMemoryStore startswith) semantics.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Union

from src.chat2.store_primitives import StoreKey

__all__ = ["SqliteChat2Primitives"]


class SqliteChat2Primitives:
    """SQLite-backed implementation of the generic-store doc/log protocol.

    Args:
        db_path: Path to the SQLite database file (or ``":memory:"``).
    """

    def __init__(self, db_path: Union[str, Path]) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.RLock()
        self._init_schema()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create the kv/logs tables from schema.sql if they are missing."""
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL").fetchone()
            self._conn.execute("PRAGMA synchronous = NORMAL").fetchone()
            # LIKE is case-insensitive for ASCII by default; StoreKey
            # prefixes are case-sensitive (like str.startswith).
            self._conn.execute("PRAGMA case_sensitive_like = ON").fetchone()
            row = self._conn.execute(
                "SELECT count(*) FROM sqlite_master"
                " WHERE type = 'table' AND name IN ('kv', 'logs')"
            ).fetchone()
            if row is not None and row[0] == 2:
                return
            schema = Path(__file__).resolve().parent / "schema.sql"
            self._conn.executescript(schema.read_text(encoding="utf-8"))
            self._conn.commit()

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

    # ------------------------------------------------------------------
    # Document ops (kv)
    # ------------------------------------------------------------------

    def read_text(self, key: Union[StoreKey, str]) -> Optional[str]:
        """Return the document at *key*, or None if it does not exist."""
        k = self._key(key)
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM kv WHERE key = ?", (k,)
            ).fetchone()
        return row[0] if row is not None else None

    def write_text(self, key: Union[StoreKey, str], text: str) -> None:
        """Atomically replace the document at *key* (upsert, one txn)."""
        k = self._key(key)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET"
                    " value = excluded.value, updated_at = excluded.updated_at",
                    (k, text, now),
                )

    def exists(self, key: Union[StoreKey, str]) -> bool:
        """Return True if *key* has a document or log rows."""
        k = self._key(key)
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM kv WHERE key = ?"
                " UNION ALL SELECT 1 FROM logs WHERE key = ?"
                " LIMIT 1",
                (k, k),
            ).fetchone()
        return row is not None

    def delete(self, key: Union[StoreKey, str]) -> None:
        """Remove *key* from both tables. No-op if it does not exist."""
        k = self._key(key)
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM kv WHERE key = ?", (k,))
                self._conn.execute("DELETE FROM logs WHERE key = ?", (k,))

    # ------------------------------------------------------------------
    # Log ops (logs)
    # ------------------------------------------------------------------

    def read_lines(self, key: Union[StoreKey, str]) -> Optional[List[str]]:
        """Return the lines of the log at *key* in append order (seq).

        Returns None if the key has no log rows (missing log).
        """
        k = self._key(key)
        with self._lock:
            rows = self._conn.execute(
                "SELECT line FROM logs WHERE key = ? ORDER BY seq", (k,)
            ).fetchall()
        if not rows:
            return None
        return [r[0] for r in rows]

    def append_lines(
        self, key: Union[StoreKey, str], lines: Iterable[str]
    ) -> None:
        """Append *lines* to the log at *key* in one transaction.

        The first line gets ``seq = COALESCE(MAX(seq), 0) + 1`` and each
        following line increments it, so append order == seq order.
        Lines are stored verbatim (no newlines are added or stripped).
        """
        k = self._key(key)
        items = list(lines)
        if not items:
            return
        with self._lock:
            with self._conn:
                start = self._conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM logs WHERE key = ?",
                    (k,),
                ).fetchone()[0]
                self._conn.executemany(
                    "INSERT INTO logs (key, seq, line) VALUES (?, ?, ?)",
                    [(k, start + i, line) for i, line in enumerate(items)],
                )

    def truncate(self, key: Union[StoreKey, str]) -> None:
        """Clear the log at *key* (all lines).

        Keeps any document stored at the same key; the log is missing
        (read_lines -> None) until the next append. No-op if absent.
        """
        k = self._key(key)
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM logs WHERE key = ?", (k,))

    # ------------------------------------------------------------------
    # Namespace
    # ------------------------------------------------------------------

    def list_keys(self, prefix: Union[StoreKey, str]) -> List[StoreKey]:
        """Return all keys (documents and logs) starting with *prefix*.

        Uses ``LIKE ... ESCAPE`` so '%' and '_' in the prefix match
        literally; case sensitivity comes from PRAGMA case_sensitive_like.
        Keys present in both tables are listed once, sorted by key.
        """
        p = self._key(prefix)
        pattern = (
            p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        with self._lock:
            rows = self._conn.execute(
                "SELECT key FROM ("
                "  SELECT key FROM kv WHERE key LIKE ? ESCAPE '\\'"
                "  UNION"
                "  SELECT key FROM logs WHERE key LIKE ? ESCAPE '\\'"
                ") ORDER BY key",
                (pattern, pattern),
            ).fetchall()
        return [StoreKey(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection (idempotent)."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SqliteChat2Primitives":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()
