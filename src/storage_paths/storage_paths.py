from pathlib import Path

class StoragePaths:
    """
    Centralised, authoritative resolver for all user-data paths.
    """

    def __init__(self, storage_root_path: str, storage_namespace: str):
        self.root = Path(storage_root_path).resolve()
        self.namespace = storage_namespace
        self.base = (self.root / self.namespace).resolve()

        # Hard guard against misconfiguration
        if not self.base.is_relative_to(self.root):
            raise ValueError("storage_namespace escapes storage_root_path")

    @property
    def contexts(self) -> Path:
        return self.base / "contexts"

    @property
    def chats(self) -> Path:
        return self.base / "chats"

    @property
    def documents(self) -> Path:
        return self.base / "documents"

    @property
    def users(self) -> Path:
        return self.base / "users"

    @property
    def indexes(self) -> Path:
        return self.base / "indexes"
    
    @property
    def agents(self) -> Path:
        return self.base / "agents"

    def resolve_relative(self, relative_path: str) -> Path:
        """
        Safely resolve a user-supplied relative path under storage base.
        Rejects absolute paths, '..', and symlink escapes.
        """
        p = (self.base / relative_path).resolve()
        if not p.is_relative_to(self.base):
            raise ValueError("Path escapes storage namespace")
        return p
