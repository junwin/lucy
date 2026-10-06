"""CurationEngine — application service for episodic memory curation.

The engine orchestrates session resolution, filtering, summarization, and digest publication. It depends on provider-neutral interfaces;
concrete storage details stay behind the galet-memory interface.
"""

from __future__ import annotations

from src.episodic import LucyEpisodicStore

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from galet.interface import LLMApi

from galet_memory import Event
from src.curation.resolver import resolve_session
from src.curation.summarizer import summarize_session
from src.curation.templates import render_template, resolve_template
from src.embeddings.facade import EmbeddingFacade
from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord

logger = logging.getLogger(__name__)


class CurationEngine:
    """High-level curation service over provider-neutral memory interfaces."""

    def __init__(
        self,
        episodic_store: LucyEpisodicStore,
        llm_api: LLMApi,
        llm_model: str = "gpt-4o-mini",
        digests_root: Optional[Path] = None,
        embedding_facade: Optional[EmbeddingFacade] = None,
        storage: Optional[EmbeddingStore] = None,
    ) -> None:
        self.episodic_store = episodic_store
        self.llm_api = llm_api
        self.llm_model = llm_model
        self.digests_root = digests_root or Path("data/digests")
        self.embedding_facade = embedding_facade
        self.storage = storage

    def curate(
        self,
        *,
        session_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        account: str,
        mode: str = "filter",
        preview: bool = True,
        publish: bool = False,
        template_name: str = "default",
        context_state_template: Optional[str] = None,
        curation_rules: Optional[Dict[str, Any]] = None,
        max_chars: int = 32000,
    ) -> Dict[str, Any]:
        session = resolve_session(
            session_id=session_id,
            friendly_name=friendly_name,
            account=account,
            episodic_store=self.episodic_store,
        )
        if session is None:
            return {
                "status": "error",
                "error": f"Session not found: friendly_name={friendly_name}, session_id={session_id}",
            }

        full_session = self.episodic_store.get_active_snapshot(
            account_name=account, session_id=session.session_id
        )
        if full_session is None:
            return {
                "status": "error",
                "error": f"Session disappeared during curation: {session.session_id}",
            }

        sid = full_session.session_id
        fn = full_session.friendly_name or sid
        events = list(full_session.events)

        if mode == "filter":
            return {"status": "error", "error": "Destructive curation filtering is no longer supported; invalidate an exchange by correlation_id instead."}
        if mode == "summarize":
            return self._mode_summarize(
                sid=sid,
                events=events,
                account=account,
                friendly_name=fn,
                template_name=template_name,
                context_state_template=context_state_template,
                preview=preview,
                publish=publish,
                max_chars=max_chars,
            )
        return {"status": "error", "error": f"Unknown mode: {mode}"}

    def _mode_summarize(
        self,
        *,
        sid: str,
        events: List[Event],
        account: str,
        friendly_name: str,
        template_name: str,
        context_state_template: Optional[str],
        preview: bool,
        publish: bool,
        max_chars: int,
    ) -> Dict[str, Any]:
        digest = summarize_session(
            events,
            llm_api=self.llm_api,
            model=self.llm_model,
            friendly_name=friendly_name,
            session_id=sid,
            account=account,
            max_chars=max_chars,
        )
        template = resolve_template(
            template_name,
            context_state_override=context_state_template,
        )
        note_text = render_template(
            template,
            friendly_name=friendly_name,
            session_id=sid,
            account=account,
            archive_path="",
            events=events,
            summary_text=digest,
        )

        if preview or not publish:
            return {
                "status": "preview",
                "note_text": note_text,
                "output_path": None,
                "session_id": sid,
            }

        output_path = self._write_digest(sid, account, note_text)
        self._maybe_embed_digest(note_text, output_path, sid, account, [event.event_id for event in events])
        return {
            "status": "published",
            "note_text": note_text,
            "output_path": str(output_path),
            "session_id": sid,
        }


    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _write_digest(self, session_id: str, account: str, note_text: str) -> Path:
        digest_dir = self.digests_root / account
        digest_dir.mkdir(parents=True, exist_ok=True)
        output_path = digest_dir / f"{session_id}_{self._timestamp()}.md"
        output_path.write_text(note_text, encoding="utf-8")
        logger.info(
            "curation: wrote digest to %s (session=%s account=%s)",
            output_path,
            session_id,
            account,
        )
        return output_path

    def _maybe_embed_digest(
        self,
        note_text: str,
        note_path: Path,
        session_id: str,
        account: str,
        source_event_ids: List[str],
    ) -> None:
        if self.embedding_facade is None or self.storage is None:
            return
        if len(note_text.strip()) < 100:
            return

        try:
            self.storage.delete_embeddings(
                namespace="digests",
                account_name=account,
                source_id=session_id,
            )
            response = self.embedding_facade.embed(
                [note_text[:32000]], model="text-embedding-3-small"
            )
            record = EmbeddingRecord(
                id=note_path.stem,
                namespace="digests",
                account_name=account,
                vector=response.embeddings[0],
                source_type="digest",
                source_id=session_id,
                source_metadata={
                    "path": str(note_path),
                    "session_id": session_id,
                    "source_event_ids": source_event_ids,
                },
            )
            self.storage.upsert_embedding(record)
        except Exception as exc:
            logger.warning("curation: failed to embed digest %s: %s", note_path.stem, exc)
