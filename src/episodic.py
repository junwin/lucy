"""Lucy composition seam for galet-memory's explicit account-scoped contracts."""
from typing import Protocol
from galet_memory import Session, SessionStore, EventStore, CurationStore


class LucyEpisodicStore(SessionStore, EventStore, CurationStore, Protocol):
    """One injected backend supplies the separate session/event/curation ports."""


def list_account_sessions(store: SessionStore, account_name: str, count: int | None = None) -> list[Session]:
    """Read account metadata across pages, optionally stopping after count records."""
    cursor = None
    selected = []
    while count is None or len(selected) < count:
        size = 100 if count is None else min(100, count - len(selected))
        page = store.list_sessions(account_name=account_name, count=size, cursor=cursor)
        selected.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    return selected
