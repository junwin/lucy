"""Archive function for curation.

Moves a session's original events to an archive location and replaces
the active session with a single digest event.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent

logger = logging.getLogger(__name__)


def archive_session(
    session_id: str,
    digest_text: str,
    *,
    chat2_store: Chat2Store,
    archive_dir: Path,
    account: str,
) -> bool:
    """Archive a session: move original events to archive, replace with digest event.

    Steps:
    1. Read all events from the session.
    2. Write them to <archive_dir>/<account>/<session_id>.jsonl
    3. Reset the session events.
    4. Add a single digest event with the digest text.

    Args:
        session_id: Session UUID.
        digest_text: The digest Markdown text to store as the replacement event.
        chat2_store: Chat2Store instance.
        archive_dir: Base archive directory (e.g. Path("data/archives")).
        account: Account name.

    Returns:
        True if successful, False otherwise.
    """
    meta = chat2_store.get_session(session_id)
    if meta is None:
        logger.warning("archive_session: session not found: %s", session_id)
        return False

    # 1) Read all events
    events: List[ChatEvent] = list(chat2_store.stream_events(session_id))
    if not events:
        logger.info("archive_session: no events to archive for session=%s", session_id)
        # Still write the digest event
        _replace_with_digest(chat2_store, session_id, digest_text)
        return True

    # 2) Write archive file
    archive_account_dir = archive_dir / account
    archive_account_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_account_dir / f"{session_id}.jsonl"

    try:
        with open(archive_path, "w", encoding="utf-8") as f:
            for e in events:
                f.write(e.model_dump_json() + "\n")
        logger.info(
            "archive_session: wrote %d events to %s",
            len(events),
            archive_path,
        )
    except Exception:
        logger.exception(
            "archive_session: failed to write archive file %s",
            archive_path,
        )
        return False

    # 3) Replace session events with digest
    _replace_with_digest(chat2_store, session_id, digest_text)

    logger.info(
        "archive_session: completed for session=%s account=%s",
        session_id,
        account,
    )
    return True


def _replace_with_digest(
    chat2_store: Chat2Store,
    session_id: str,
    digest_text: str,
) -> None:
    """Reset session events and add a single digest event."""
    chat2_store.reset_events(session_id)
    digest_event = ChatEvent(
        role="system",
        actor="curation",
        kind="summary",
        payload=digest_text,
        metadata={"curation_mode": "archive", "archived_at": datetime.now(timezone.utc).isoformat()},
    )
    chat2_store.add_event(session_id, digest_event)
    logger.info("archive_session: replaced events with digest for session=%s", session_id)
