"""CurationEngine — high-level orchestration for chat curation.

Wraps the resolver, summarizer, archiver, and template renderer into a
single callable interface used by the curate_chat handler and CLI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.curation.resolver import resolve_session
from src.curation.templates import render_template, resolve_template
from src.curation.summarizer import summarize_session
from src.curation.archiver import archive_session
from src.embeddings.facade import EmbeddingFacade
from src.llm.interface import LLMApi
from src.storage.models import EmbeddingRecord

logger = logging.getLogger(__name__)


class CurationEngine:
    """High-level curation orchestrator.

    Args:
        chat2_store: Chat2Store instance.
        llm_api: LLM API instance (for summarize mode).
        llm_model: Model name for summarization.
        digests_root: Base path for digest output (e.g. Path("data/digests")).
        archives_root: Base path for archive output (e.g. Path("data/archives")).
        chats_index_path: Optional path to index.json for friendly-name resolution.
        embedding_facade: Optional EmbeddingFacade to embed digests at creation time.
        storage: Optional Storage to persist embedding records.
    """

    def __init__(
        self,
        chat2_store: Chat2Store,
        llm_api: LLMApi,
        llm_model: str = "gpt-4o-mini",
        digests_root: Optional[Path] = None,
        archives_root: Optional[Path] = None,
        chats_index_path: Optional[Path] = None,
        embedding_facade: Optional[EmbeddingFacade] = None,
        storage: Optional[Any] = None,
    ) -> None:
        self.chat2_store = chat2_store
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
    ) -> Dict[str, Any]:
        """Run curation on a session.

        Args:
            session_id: Direct session UUID.
            friendly_name: Friendly name to resolve.
            account: Account name.
            mode: "filter", "summarize", or "archive".
            preview: If True, return note_text without writing.
            publish: If True, write digest to disk.
            template_name: Named template to use.
            context_state_template: Optional template override from ContextState.
            curation_rules: Rules dict for filter mode (remove_kinds, keep_roles, deduplicate).

        Returns:
            Result dict with status, note_text, output_path, etc.
        """
        # --- Resolve session ---
        meta = resolve_session(
            session_id=session_id,
            friendly_name=friendly_name,
            account=account,
            chat2_store=self.chat2_store,
            chats_index_path=self.chats_index_path,
        )
        if meta is None:
            return {
                "status": "error",
                "error": f"Session not found: friendly_name={friendly_name}, session_id={session_id}",
            }

        sid = meta.session_id
        fn = meta.friendly_name or sid

        # --- Read events ---
        events: List[ChatEvent] = list(self.chat2_store.stream_events(sid))

        # --- Execute mode ---
        if mode == "filter":
            return self._mode_filter(
                sid=sid,
                events=events,
                rules=curation_rules or {},
                account=account,
                friendly_name=fn,
            )

        elif mode == "summarize":
            return self._mode_summarize(
                sid=sid,
                events=events,
                account=account,
                friendly_name=fn,
                template_name=template_name,
                context_state_template=context_state_template,
                preview=preview,
                publish=publish,
            )

        elif mode == "archive":
            return self._mode_archive(
                sid=sid,
                events=events,
                account=account,
                friendly_name=fn,
                template_name=template_name,
                context_state_template=context_state_template,
                preview=preview,
                publish=publish,
            )

        else:
            return {
                "status": "error",
                "error": f"Unknown mode: {mode}",
            }

    # ------------------------------------------------------------------
    # Mode implementations
    # ------------------------------------------------------------------

    def _mode_filter(
        self,
        sid: str,
        events: List[ChatEvent],
        rules: Dict[str, Any],
        account: str,
        friendly_name: str,
    ) -> Dict[str, Any]:
        """Apply rule-based filtering (same as existing curate_session behavior)."""
        remove_kinds: List[str] = rules.get("remove_kinds", [])
        keep_roles: List[str] = rules.get("keep_roles", [])
        deduplicate: bool = rules.get("deduplicate", False)

        original_count = len(events)
        filtered: List[ChatEvent] = []
        removed: Dict[str, int] = {"by_kind": 0, "by_role": 0, "duplicates": 0}
        seen_payloads: set = set()

        for e in events:
            if remove_kinds and e.kind in remove_kinds:
                removed["by_kind"] += 1
                continue
            if keep_roles and e.role not in keep_roles:
                removed["by_role"] += 1
                continue
            if deduplicate:
                payload_key = (
                    str(e.payload)
                    if isinstance(e.payload, str)
                    else json.dumps(e.payload, sort_keys=True)
                )
                if payload_key in seen_payloads:
                    removed["duplicates"] += 1
                    continue
                seen_payloads.add(payload_key)
            filtered.append(e)

        # Rewrite events
        self.chat2_store.reset_events(sid)
        for e in filtered:
            self.chat2_store.add_event(sid, e)

        return {
            "status": "published",
            "note_text": "",
            "output_path": None,
            "session_id": sid,
            "summary": {
                "original_count": original_count,
                "kept_count": len(filtered),
                "removed_count": original_count - len(filtered),
                "removed": removed,
            },
        }

    def _mode_summarize(
        self,
        sid: str,
        events: List[ChatEvent],
        account: str,
        friendly_name: str,
        template_name: str,
        context_state_template: Optional[str],
        preview: bool,
        publish: bool,
    ) -> Dict[str, Any]:
        """Generate an LLM digest and optionally write it."""
        # Generate digest
        digest = summarize_session(
            events,
            llm_api=self.llm_api,
            model=self.llm_model,
            friendly_name=friendly_name,
            session_id=sid,
            account=account,
        )

        # Resolve and render template (no archive for summarize mode)
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

        if preview:
            return {
                "status": "preview",
                "note_text": note_text,
                "output_path": None,
                "session_id": sid,
            }

        if publish:
            output_path = self._write_digest(sid, account, note_text)
            self._maybe_embed_digest(note_text, output_path, sid, account)
            return {
                "status": "published",
                "note_text": note_text,
                "output_path": str(output_path),
                "session_id": sid,
            }

        return {
            "status": "preview",
            "note_text": note_text,
            "output_path": None,
            "session_id": sid,
        }

    def _mode_archive(
        self,
        sid: str,
        events: List[ChatEvent],
        account: str,
        friendly_name: str,
        template_name: str,
        context_state_template: Optional[str],
        preview: bool,
        publish: bool,
    ) -> Dict[str, Any]:
        """Summarize, archive original events, replace with digest."""
        # Generate digest
        digest = summarize_session(
            events,
            llm_api=self.llm_api,
            model=self.llm_model,
            friendly_name=friendly_name,
            session_id=sid,
            account=account,
        )

        # Compute archive path for the template reference.
        # Use a glob since the exact timestamp is assigned at archive time.
        archive_ref = str(self.archives_root / account / f"{sid}_*.jsonl")

        # Resolve and render template
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

        # Write digest (timestamped)
        output_path = None
        if publish:
            output_path = self._write_digest(sid, account, note_text)
            self._maybe_embed_digest(note_text, output_path, sid, account)

        # Archive original events (timestamped) and replace with digest
        archived = archive_session(
            sid,
            digest,
            chat2_store=self.chat2_store,
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        """Return a compact UTC timestamp string for filenames."""
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _write_digest(self, session_id: str, account: str, note_text: str) -> Path:
        """Write digest to <digests_root>/<account>/<session_id>_<timestamp>.md."""
        digest_dir = self.digests_root / account
        digest_dir.mkdir(parents=True, exist_ok=True)
        ts = self._timestamp()
        output_path = digest_dir / f"{session_id}_{ts}.md"
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
        """Embed the digest text for semantic search, if embedding deps are available.

        Gracefully skips if embedding_facade or storage is not configured,
        or if the digest is too short to be useful.
        """
        if self.embedding_facade is None or self.storage is None:
            return

        if len(note_text.strip()) < 100:
            logger.debug("curation: skipping embed — digest too short (%d chars)", len(note_text))
            return

        try:
            # Before upserting, delete any existing embeddings for this session.
            # This prevents duplicate near-identical vectors when a session is
            # re-curated (summarize/archive with publish) multiple times.
            self.storage.delete_embeddings(
                namespace="digests",
                account_name=account,
                source_id=session_id,
            )

            # Truncate to a safe limit (most embedding models handle ~8k tokens)
            text = note_text[:32000]

            resp = self.embedding_facade.embed([text], model="text-embedding-3-small")
            vector = resp.embeddings[0]

            record = EmbeddingRecord(
                id=note_path.stem,
                namespace="digests",
                account_name=account,
                vector=vector,
                source_type="digest",
                source_id=session_id,
                source_metadata={
                    "path": str(note_path),
                    "session_id": session_id,
                },
            )
            self.storage.upsert_embedding(record)
            logger.info(
                "curation: embedded digest %s (session=%s)",
                note_path.stem,
                session_id,
            )
        except Exception as e:
            logger.warning("curation: failed to embed digest %s: %s", note_path.stem, e)
