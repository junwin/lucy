"""CurationEngine — application service for episodic memory curation.

The engine orchestrates session resolution, filtering, summarization, archive
artifacts and digest publication. It depends on provider-neutral interfaces;
concrete Chat2/JFS/SQLite details stay behind the episodic adapter.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from galet.interface import LLMApi

from src.coala_memory.episodic import EpisodicEvent, EpisodicMemoryManager
from src.curation.archiver import archive_session
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
        episodic_store: EpisodicMemoryManager,
        llm_api: LLMApi,
        llm_model: str = "gpt-4o-mini",
        digests_root: Optional[Path] = None,
        archives_root: Optional[Path] = None,
        chats_index_path: Optional[Path] = None,
        embedding_facade: Optional[EmbeddingFacade] = None,
        storage: Optional[EmbeddingStore] = None,
    ) -> None:
        self.episodic_store = episodic_store
        self.llm_api = llm_api
        self.llm_model = llm_model
        self.digests_root = digests_root or Path("data/digests")
        self.archives_root = archives_root or Path("data/archives")
        self.chats_index_path = chats_index_path
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
            chats_index_path=self.chats_index_path,
        )
        if session is None:
            return {
                "status": "error",
                "error": f"Session not found: friendly_name={friendly_name}, session_id={session_id}",
            }

        full_session = self.episodic_store.get_session(
            session.session_id, include_events=True
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
            return self._mode_filter(
                sid=sid,
                events=events,
                rules=curation_rules or {},
            )
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
        if mode == "archive":
            return self._mode_archive(
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

    def _mode_filter(
        self,
        *,
        sid: str,
        events: List[EpisodicEvent],
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        remove_kinds: List[str] = rules.get("remove_kinds", [])
        keep_roles: List[str] = rules.get("keep_roles", [])
        deduplicate: bool = rules.get("deduplicate", False)

        filtered: List[EpisodicEvent] = []
        removed: Dict[str, int] = {"by_kind": 0, "by_role": 0, "duplicates": 0}
        seen_payloads: set[str] = set()

        for event in events:
            if remove_kinds and event.kind in remove_kinds:
                removed["by_kind"] += 1
                continue
            if keep_roles and event.role not in keep_roles:
                removed["by_role"] += 1
                continue
            if deduplicate:
                payload_key = (
                    event.content
                    if isinstance(event.content, str)
                    else json.dumps(event.content, sort_keys=True)
                )
                if payload_key in seen_payloads:
                    removed["duplicates"] += 1
                    continue
                seen_payloads.add(payload_key)
            filtered.append(event)

        self.episodic_store.reset_session(sid)
        for event in filtered:
            self.episodic_store.append_event(sid, event)

        return {
            "status": "published",
            "note_text": "",
            "output_path": None,
            "session_id": sid,
            "summary": {
                "original_count": len(events),
                "kept_count": len(filtered),
                "removed_count": len(events) - len(filtered),
                "removed": removed,
            },
        }

    def _mode_summarize(
        self,
        *,
        sid: str,
        events: List[EpisodicEvent],
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
        self._maybe_embed_digest(note_text, output_path, sid, account)
        return {
            "status": "published",
            "note_text": note_text,
            "output_path": str(output_path),
            "session_id": sid,
        }

    def _mode_archive(
        self,
        *,
        sid: str,
        events: List[EpisodicEvent],
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
        archive_ref = str(self.archives_root / account / f"{sid}_*.jsonl")
        template = resolve_template(
            template_name,
            context_state_override=context_state_template,
        )
        note_text = render_template(
            template,
            friendly_name=friendly_name,
            session_id=sid,
            account=account,
            archive_path=archive_ref,
            events=events,
            summary_text=digest,
        )

        if preview:
            return {
                "status": "preview",
                "note_text": note_text,
                "output_path": None,
                "session_id": sid,
            }

        output_path = None
        if publish:
            output_path = self._write_digest(sid, account, note_text)
            self._maybe_embed_digest(note_text, output_path, sid, account)

        archived = archive_session(
            sid,
            digest,
            episodic_store=self.episodic_store,
            archive_dir=self.archives_root,
            account=account,
        )
        if not archived:
            return {
                "status": "error",
                "error": f"Failed to archive session {sid}",
                "note_text": note_text,
                "session_id": sid,
            }

        return {
            "status": "archived",
            "note_text": note_text,
            "output_path": str(output_path) if output_path else None,
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
                },
            )
            self.storage.upsert_embedding(record)
        except Exception as exc:
            logger.warning("curation: failed to embed digest %s: %s", note_path.stem, exc)
