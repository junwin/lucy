"""Archive support for curation.

The curation layer owns the archive artifact, but reads and rewrites the active
session only through the provider-neutral episodic interface.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.coala_memory.episodic import EpisodicEvent, EpisodicMemoryManager

logger = logging.getLogger(__name__)


def _next_archive_path(archive_account_dir: Path, session_id: str) -> Path:
    existing = sorted(archive_account_dir.glob(f"{session_id}_*.jsonl"))
    if not existing:
        return archive_account_dir / f"{session_id}_1.jsonl"

    max_n = 0
    for path in existing:
        try:
            max_n = max(max_n, int(path.stem.rsplit("_", 1)[-1]))
        except ValueError:
            pass
    return archive_account_dir / f"{session_id}_{max_n + 1}.jsonl"


def _archive_record(event: EpisodicEvent) -> Dict[str, Any]:
    """Return a stable JSONL representation without depending on Chat2 models.

    Field names intentionally match the existing ChatEvent archive shape where
    possible so existing archives remain easy to inspect and migrate.
    """
    return {
        "event_id": event.event_id or None,
        "ts": event.created_at.isoformat() if event.created_at else None,
        "role": event.role,
        "actor": event.actor,
        "kind": event.kind,
        "payload": event.content,
        "metadata": dict(event.metadata or {}),
    }


def archive_session(
    session_id: str,
    digest_text: str,
    *,
    episodic_store: EpisodicMemoryManager,
    archive_dir: Path,
    account: str,
) -> bool:
    """Archive original events and replace the active session with a digest."""
    session = episodic_store.get_session(session_id, include_events=True)
    if session is None:
        logger.warning("archive_session: session not found: %s", session_id)
        return False

    events: List[EpisodicEvent] = list(session.events)
    if events:
        archive_account_dir = archive_dir / account
        archive_account_dir.mkdir(parents=True, exist_ok=True)
        archive_path = _next_archive_path(archive_account_dir, session_id)
        try:
            with archive_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(
                        json.dumps(_archive_record(event), ensure_ascii=False) + "\n"
                    )
            logger.info(
                "archive_session: wrote %d events to %s",
                len(events),
                archive_path,
            )
        except Exception:
            logger.exception(
                "archive_session: failed to write archive file %s", archive_path
            )
            return False

    _replace_with_digest(episodic_store, session_id, digest_text)
    logger.info(
        "archive_session: completed for session=%s account=%s",
        session_id,
        account,
    )
    return True


def _replace_with_digest(
    episodic_store: EpisodicMemoryManager,
    session_id: str,
    digest_text: str,
) -> None:
    episodic_store.reset_session(session_id)
    episodic_store.append_event(
        session_id,
        EpisodicEvent(
            role="system",
            actor="curation",
            kind="summary",
            content=digest_text,
            metadata={
                "curation_mode": "archive",
                "archived_at": datetime.now(timezone.utc).isoformat(),
            },
        ),
    )
    logger.info("archive_session: replaced events with digest for session=%s", session_id)
