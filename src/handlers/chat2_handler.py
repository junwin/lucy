"""
Chat2 handler for agent tool access.

Provides the agent with direct CRUD operations on chat2 sessions:
- reset_chat: clear all events, keep session metadata
- search_sessions: find sessions by query string in events
- curate_session: filter/transform events in a session
- get_session: retrieve session metadata + events
- list_sessions: list sessions with optional filters
- delete_session: delete a session and its events
- update_session: update session metadata fields
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent

logger = logging.getLogger(__name__)


class Chat2Handler(HandlerV2):
    """Handler for chat2 session management by the agent."""

    NAME = "chat2_handler"

    def __init__(self, config: ConfigManager):
        self.config = config
        self.chat2_store = self._build_store()

    def _build_store(self) -> Chat2Store:
        """Construct a Chat2Store from config."""
        from pathlib import Path

        from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
        from src.chat2.sqlite import SqliteChat2Primitives
        from src.storage.json_file_storage import JsonFileStorage
        from src.storage_paths.storage_paths import StoragePaths

        config = self.config
        backend = str(config.get("chat2_store_backend", "") or "").strip().lower()
        if backend == "sqlite":
            db_path = config.get("chat2_store_db_path")
            if not db_path:
                storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
                storage_namespace = config.get("storage_namespace") or "data"
                db_path = str(Path(storage_root) / storage_namespace / "chat2.sqlite")
            return Chat2Store(SqliteChat2Primitives(db_path))
        if not backend or backend == "jsonl":
            storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
            storage_namespace = config.get("storage_namespace") or "data"
            sp = StoragePaths(storage_root, storage_namespace)
            storage = JsonFileStorage(sp)
            return Chat2Store(JfsChat2Primitives(storage))
        raise ValueError(
            "Unknown chat2_store_backend %r: expected 'jsonl' or 'sqlite'" % backend
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Manage chat sessions: reset (clear events, keep meta), "
                "search sessions by query string, curate events, "
                "or standard CRUD (get, list, delete, update)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "reset_chat",
                            "search_sessions",
                            "curate_session",
                            "get_session",
                            "list_sessions",
                            "delete_session",
                            "update_session",
                        ],
                        "description": "The operation to perform.",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "UUID of the session (required for reset, get, delete, update, curate).",
                        "default": "",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search string to find in session events (for search_sessions).",
                        "default": "",
                    },
                    "account_name": {
                        "type": "string",
                        "description": "Filter by account name.",
                        "default": "",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "Filter by agent name.",
                        "default": "",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 20).",
                        "default": 20,
                    },
                    "patch_fields": {
                        "type": "string",
                        "description": "JSON string of fields to update (for update_session).",
                        "default": "",
                    },
                    "curation_rules": {
                        "type": "string",
                        "description": (
                            "JSON string of curation rules (for curate_session). "
                            "Supports: remove_kinds (list of kind strings to remove), "
                            "keep_roles (list of role strings to keep), "
                            "deduplicate (bool)."
                        ),
                        "default": "",
                    },
                },
                "required": [
                    "action",
                    "session_id",
                    "query",
                    "account_name",
                    "agent_name",
                    "limit",
                    "patch_fields",
                    "curation_rules",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "session_id": {"type": "string"},
                "session": {"type": "object"},
                "sessions": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "summary": {"type": "object"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:
        action = (args.get("action") or "").strip().lower()
        session_id = (args.get("session_id") or "").strip()
        query = (args.get("query") or "").strip()
        filter_account = (args.get("account_name") or "").strip()
        filter_agent = (args.get("agent_name") or "").strip()
        limit = int(args.get("limit", 20))
        patch_fields_raw = args.get("patch_fields") or ""
        curation_rules_raw = args.get("curation_rules") or ""

        logger.info(
            "chat2_handler input account=%s action=%s session_id=%s",
            account_name,
            action,
            session_id,
        )

        try:
            if action == "reset_chat":
                return self._reset_chat(session_id)
            elif action == "search_sessions":
                return self._search_sessions(query, filter_account, filter_agent, limit)
            elif action == "curate_session":
                return self._curate_session(session_id, curation_rules_raw)
            elif action == "get_session":
                return self._get_session(session_id)
            elif action == "list_sessions":
                return self._list_sessions(filter_account, filter_agent, limit)
            elif action == "delete_session":
                return self._delete_session(session_id)
            elif action == "update_session":
                return self._update_session(session_id, patch_fields_raw)
            else:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "error": f"Unknown action: {action}",
                }
        except Exception as e:
            logger.exception("chat2_handler failed action=%s", action)
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": f"{type(e).__name__}: {e}",
            }

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _reset_chat(self, session_id: str) -> Dict[str, Any]:
        """Clear all events from a session, preserving metadata."""
        if not session_id:
            return {"ok": False, "tool": self.NAME, "action": "reset_chat", "error": "session_id is required"}

        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return {"ok": False, "tool": self.NAME, "action": "reset_chat", "error": f"Session not found: {session_id}"}

        self.chat2_store.reset_events(session_id)
        updated_meta = self.chat2_store.get_session(session_id)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "reset_chat",
            "session_id": session_id,
            "session": self._meta_to_dict(updated_meta) if updated_meta else None,
        }

    def _search_sessions(
        self,
        query: str,
        account_name: str,
        agent_name: str,
        limit: int,
    ) -> Dict[str, Any]:
        """Search sessions by query string in events."""
        if not query:
            return {"ok": False, "tool": self.NAME, "action": "search_sessions", "error": "query is required"}

        sessions = self.chat2_store.list_sessions(
            account_name=account_name or None,
            agent_name=agent_name or None,
            limit=limit,
        )

        matching: List[Dict[str, Any]] = []
        query_lower = query.lower()

        for s in sessions:
            events = list(self.chat2_store.stream_events(s.session_id))
            matched_events = []
            for e in events:
                payload_str = str(e.payload) if isinstance(e.payload, str) else json.dumps(e.payload)
                if query_lower in payload_str.lower():
                    matched_events.append({
                        "event_id": e.event_id,
                        "role": e.role,
                        "kind": e.kind,
                        "snippet": payload_str[:200],
                    })
            if matched_events:
                matching.append({
                    "session_id": s.session_id,
                    "account_name": s.account_name,
                    "agent_name": s.agent_name,
                    "friendly_name": s.friendly_name,
                    "updated_at": s.updated_at.isoformat(),
                    "matched_events": len(matched_events),
                    "event_snippets": matched_events[:5],  # limit snippets per session
                })

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "search_sessions",
            "query": query,
            "sessions": matching,
            "total_matches": len(matching),
        }

    def _curate_session(self, session_id: str, curation_rules_raw: str) -> Dict[str, Any]:
        """Apply curation rules to a session's events."""
        if not session_id:
            return {"ok": False, "tool": self.NAME, "action": "curate_session", "error": "session_id is required"}

        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return {"ok": False, "tool": self.NAME, "action": "curate_session", "error": f"Session not found: {session_id}"}

        # Parse curation rules
        rules: Dict[str, Any] = {}
        if curation_rules_raw:
            try:
                rules = json.loads(curation_rules_raw)
            except json.JSONDecodeError as e:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "action": "curate_session",
                    "error": f"Invalid curation_rules JSON: {e}",
                }

        remove_kinds: List[str] = rules.get("remove_kinds", [])
        keep_roles: List[str] = rules.get("keep_roles", [])
        deduplicate: bool = rules.get("deduplicate", False)

        # Read all events
        all_events = list(self.chat2_store.stream_events(session_id))
        original_count = len(all_events)

        # Apply filters
        filtered: List[ChatEvent] = []
        removed: Dict[str, int] = {"by_kind": 0, "by_role": 0, "duplicates": 0}
        seen_payloads: set = set()

        for e in all_events:
            # Remove by kind
            if remove_kinds and e.kind in remove_kinds:
                removed["by_kind"] += 1
                continue

            # Keep only specified roles
            if keep_roles and e.role not in keep_roles:
                removed["by_role"] += 1
                continue

            # Deduplicate by payload content
            if deduplicate:
                payload_key = str(e.payload) if isinstance(e.payload, str) else json.dumps(e.payload, sort_keys=True)
                if payload_key in seen_payloads:
                    removed["duplicates"] += 1
                    continue
                seen_payloads.add(payload_key)

            filtered.append(e)

        # Rewrite events file
        self.chat2_store.reset_events(session_id)
        for e in filtered:
            self.chat2_store.add_event(session_id, e)

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "curate_session",
            "session_id": session_id,
            "summary": {
                "original_count": original_count,
                "kept_count": len(filtered),
                "removed_count": original_count - len(filtered),
                "removed": removed,
            },
        }

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session metadata and events."""
        if not session_id:
            return {"ok": False, "tool": self.NAME, "action": "get_session", "error": "session_id is required"}

        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return {"ok": False, "tool": self.NAME, "action": "get_session", "error": f"Session not found: {session_id}"}

        events = list(self.chat2_store.stream_events(session_id))
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "get_session",
            "session_id": session_id,
            "session": self._meta_to_dict(meta),
            "events": [self._event_to_dict(e) for e in events],
            "event_count": len(events),
        }

    def _list_sessions(self, account_name: str, agent_name: str, limit: int) -> Dict[str, Any]:
        """List sessions with optional filters."""
        sessions = self.chat2_store.list_sessions(
            account_name=account_name or None,
            agent_name=agent_name or None,
            limit=limit,
        )
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "list_sessions",
            "sessions": [self._meta_to_dict(s) for s in sessions],
            "total": len(sessions),
        }

    def _delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a session and its events."""
        if not session_id:
            return {"ok": False, "tool": self.NAME, "action": "delete_session", "error": "session_id is required"}

        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return {"ok": False, "tool": self.NAME, "action": "delete_session", "error": f"Session not found: {session_id}"}

        self.chat2_store.delete_session(session_id)
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "delete_session",
            "session_id": session_id,
        }

    def _update_session(self, session_id: str, patch_fields_raw: str) -> Dict[str, Any]:
        """Update session metadata fields."""
        if not session_id:
            return {"ok": False, "tool": self.NAME, "action": "update_session", "error": "session_id is required"}

        meta = self.chat2_store.get_session(session_id)
        if meta is None:
            return {"ok": False, "tool": self.NAME, "action": "update_session", "error": f"Session not found: {session_id}"}

        if not patch_fields_raw:
            return {"ok": False, "tool": self.NAME, "action": "update_session", "error": "patch_fields is required"}

        try:
            patch_fields = json.loads(patch_fields_raw)
        except json.JSONDecodeError as e:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "update_session",
                "error": f"Invalid patch_fields JSON: {e}",
            }

        if not isinstance(patch_fields, dict):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "update_session",
                "error": "patch_fields must be a JSON object",
            }

        # Map friendly field names to internal field names
        field_map = {
            "friendly_name": "friendly_name",
            "friendlyName": "friendly_name",
            "tags": "tags",
            "metadata": "metadata",
        }

        mapped_patch: Dict[str, Any] = {}
        for key, value in patch_fields.items():
            internal_key = field_map.get(key, key)
            mapped_patch[internal_key] = value

        updated = self.chat2_store.update_session(session_id, **mapped_patch)
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "update_session",
            "session_id": session_id,
            "session": self._meta_to_dict(updated),
        }

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meta_to_dict(meta) -> Dict[str, Any]:
        """Convert ChatSessionMeta to a plain dict."""
        return {
            "session_id": meta.session_id,
            "account_name": meta.account_name,
            "agent_name": meta.agent_name,
            "friendly_name": meta.friendly_name,
            "session_type": meta.session_type,
            "created_at": meta.created_at.isoformat(),
            "updated_at": meta.updated_at.isoformat(),
            "tags": meta.tags,
            "metadata": meta.metadata,
        }

    @staticmethod
    def _event_to_dict(event: ChatEvent) -> Dict[str, Any]:
        """Convert ChatEvent to a plain dict."""
        return {
            "event_id": event.event_id,
            "ts": event.ts.isoformat(),
            "role": event.role,
            "actor": event.actor,
            "kind": event.kind,
            "payload": event.payload,
            "metadata": event.metadata,
        }
