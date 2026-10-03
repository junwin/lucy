"""Generic SQLite document/log primitives used by the embedding backend.

Episodic sessions use galet-memory's relational SQLite store.
"""

from src.chat2.sqlite.backend import SqliteChat2Primitives

__all__ = ["SqliteChat2Primitives"]
