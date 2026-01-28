from pathlib import Path

class StoragePaths:
    """
    Centralised, authoritative resolver for all user-data paths.

    NOTE: Index files are no longer stored in a top-level "indexes" directory.
    Index files are stored within each domain directory alongside their
    domain data. For example: chats/<account>/index.json (contexts follow
    the same pattern).
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
    def tasklists(self) -> Path:
        return self.base / "tasklists"

    @property
    def users(self) -> Path:
        return self.base / "users"

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

    # New helpers to build domain-local index paths. Callers should store
    # index files inside the appropriate domain directory (e.g.,
    # chats/<account>/index.json) rather than relying on a top-level indexes
    # directory.
    def index_for(self, domain: str, account: str, filename: str = "index.json") -> Path:
        """
        Return the canonical path for an index file for a given domain and
        account (or sub-namespace).

        Example: storage.index_for('chats', 'alice') -> <base>/chats/alice/index.json

        This replaces the old StoragePaths.indexes top-level directory.
        """
        if not domain or not account:
            raise ValueError("domain and account must be provided")
        return self.base / domain / account / filename

    def domain_index(self, domain: str, *subpaths: str) -> Path:
        """
        Flexible builder for domain-local index paths. Pass the domain name
        followed by any additional path components. Example:

            storage.domain_index('documents', 'doc123', 'index.json')

        resolves to: <base>/documents/doc123/index.json
        """
        if not domain:
            raise ValueError("domain must be provided")
        p = self.base / domain
        for part in subpaths:
            p = p / part
        return p
