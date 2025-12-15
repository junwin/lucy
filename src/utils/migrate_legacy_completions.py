import json
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional

INPUT_PATH = Path("data/completions/lucy_junwin_conv.json")
OUT_BASE   = Path("data")  # writes into OUT_BASE / chats / <account_name> / *.json


def parse_dt_utc(dt_str: str) -> datetime:
    """
    Parse legacy timestamps like:
      - "2023-06-07T22:12:14.041985Z"
      - "2023-06-07T22:12:14Z"
    Return an offset-aware datetime in UTC.
    """
    s = (dt_str or "").strip()
    if not s:
        return datetime.now(timezone.utc)

    # Convert trailing Z to +00:00 for fromisoformat compatibility
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def iso_utc(dt: datetime) -> str:
    """Return ISO string with +00:00 (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def safe_first_line(text: str, max_len: int = 80) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    if not line:
        return "Conversation"
    return (line[:max_len] + "…") if len(line) > max_len else line


def migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None:
    records: List[Dict[str, Any]] = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    # Group by conversation_id
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        conv_id = rec.get("conversation_id") or "unknown"
        groups[conv_id].append(rec)

    out_dir = OUT_BASE / "chats" / account_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # New: richer index entries (not just id -> friendly_name)
    index: Dict[str, Dict[str, Any]] = {}

    for conv_id, recs in groups.items():
        # sort turns by timestamp (string sort works for ISO-ish, but we’ll also compute dt later)
        recs.sort(key=lambda r: r.get("utc_timestamp") or "")

        all_tags = set()
        legacy_completion_ids: List[str] = []
        timestamps: List[datetime] = []
        messages_out: List[Dict[str, Any]] = []

        for turn_index, rec in enumerate(recs):
            legacy_id = rec.get("id")
            if legacy_id:
                legacy_completion_ids.append(str(legacy_id))

            ts_str = rec.get("utc_timestamp")
            if ts_str:
                dt = parse_dt_utc(ts_str)
                timestamps.append(dt)
                ts_norm = iso_utc(dt)
            else:
                ts_norm = None

            for t in rec.get("tags", []) or []:
                all_tags.add(t)

            for msg_i, msg in enumerate(rec.get("messages", []) or []):
                role = msg.get("role") or "user"
                content = msg.get("content") or ""

                msg_meta = {
                    "legacy_completion_id": legacy_id,
                    "turn_index": turn_index,
                    "turn_message_index": msg_i,
                }
                if role == "user":
                    msg_meta["enriched"] = False

                messages_out.append({
                    "role": role,
                    "content": content,
                    "utc_timestamp": ts_norm,  # best available: turn timestamp
                    "metadata": msg_meta
                })

        created_at = iso_utc(min(timestamps)) if timestamps else iso_utc(datetime.now(timezone.utc))
        updated_at = iso_utc(max(timestamps)) if timestamps else created_at

        first_user_content = next((m["content"] for m in messages_out if m["role"] == "user"), "Conversation")
        friendly_name = f"Conversation: {safe_first_line(first_user_content)}"

        session_id = f"conv_{conv_id}"

        session_obj = {
            "id": session_id,
            "account_name": account_name,
            "agent_name": agent_name,
            "friendly_name": friendly_name,
            "created_at": created_at,
            "updated_at": updated_at,
            "messages": messages_out,
            "tags": sorted(all_tags),

            "summary": None,
            "importance_score": 0.5,
            "include_in_context": True,

            "metadata": {
                "source": "lucy_legacy_completion",
                "conversation_id": conv_id,
                "legacy_completion_ids": legacy_completion_ids,
                "model": None
            }
        }

        # Write chat session file: <id>.json (stable)
        (out_dir / f"{session_id}.json").write_text(
            json.dumps(session_obj, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Write richer index entry (fast list/filter/sort later)
        index[session_id] = {
            "friendly_name": friendly_name,
            "agent_name": agent_name,
            "account_name": account_name,
            "updated_at": updated_at,
            "include_in_context": True,
        }

    # Write index.json
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Migrated {len(groups)} conversations -> {out_dir} ({len(index)} sessions)")


if __name__ == "__main__":
    migrate()
