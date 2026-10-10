"""Resolve reusable image references from the account-owned conversation."""

import json
from pathlib import Path
from urllib.parse import quote

from src.http_endpoints.upload_endpoints import get_image_download_impl


class ConversationAttachments:
    def __init__(self, config, store):
        self.config = config
        self.store = store

    def images(self, *, account_name, session_id):
        if self.store is None:
            raise ValueError("Conversation storage is unavailable")
        session = self.store.get_session(account_name=account_name, session_id=session_id)
        if session is None or session.account_name != account_name:
            raise ValueError("Conversation not found for this account")
        # Transcript includes archived turns but excludes invalidated exchanges.
        # Image discovery must not depend on the recent-message prompt window.
        snapshot = self.store.get_transcript_snapshot(
            account_name=account_name, session_id=session_id,
        )
        references = []
        seen = set()
        last_videos = {}
        for event in reversed(snapshot.events):
            if event.kind == "generated_video" and isinstance(event.content, dict):
                source = event.content.get("source_image_id")
                if isinstance(source, str) and source not in last_videos:
                    last_videos[source] = event.content.get("video_id")
                continue
            if event.kind == "user_message":
                ids = (event.metadata or {}).get("image_ids", [])
                origin = "uploaded"
            elif event.kind == "generated_image" and isinstance(event.content, dict):
                ids = [event.content.get("image_id")]
                origin = "generated"
            else:
                continue
            if not isinstance(ids, (list, tuple)):
                continue
            for position, image_id in enumerate(ids, 1):
                if not isinstance(image_id, str) or image_id in seen:
                    continue
                path, body, status = get_image_download_impl(self.config, account_name, image_id)
                if status != 200:
                    continue
                image_id = body["id"]
                if image_id in seen:
                    continue
                seen.add(image_id)
                metadata_path = Path(path).with_suffix(".json")
                with metadata_path.open(encoding="utf-8") as handle:
                    metadata = json.load(handle)
                references.append({
                    "image_id": image_id,
                    "filename": str(metadata.get("original_filename") or Path(path).name)[:200],
                    "mime_type": body["mime_type"],
                    "origin": origin,
                    "event_id": event.event_id,
                    "correlation_ids": list(event.correlation_ids),
                    "position": position,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                    "size_bytes": metadata.get("size_bytes"),
                    "preview_url": f"/download/image/{image_id}?accountName={quote(account_name, safe='')}",
                    "path": f"images/{account_name}/{Path(path).name}",
                })
        for reference in references:
            reference["last_video_id"] = last_videos.get(reference["image_id"])
        return references
