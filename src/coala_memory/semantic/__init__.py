"""Local semantic implementation; contracts come from galet_memory.semantic."""

from .sqlite_vec_memory import SqliteVecSemanticMemory

__all__ = ["SqliteVecSemanticMemory"]
