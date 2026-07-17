#!/usr/bin/env python3
"""
Extract a deduplicated corpus of user prompts from all chat sessions.

Reads both old-format (data/chats/<account>/*.json) and new-format
(data/chat2/sessions/<uuid>/events.jsonl) sessions.

Output: data/eval/corpus.json — a list of unique prompt objects.

Each prompt includes:
    - text, text_length, source, session_id, friendly_name, agent_name, utc_timestamp
    - num_matching_docs (int, default 0): updated by eval_enrichment.py
    - exclude (bool, default false): set by mark_excluded_prompts.py

Usage:
    python scripts/extract_prompt_corpus.py --account junwin
    python scripts/extract_prompt_corpus.py --account junwin --output data/eval/corpus.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the repo root is on sys.path so imports work
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
from src.chat2.facade import Chat2Store
from src.config_manager import ConfigManager
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths

logger = logging.getLogger(__name__)


def _build_store(config: ConfigManager) -> Chat2Store:
    """Construct a Chat2Store from config (for new-format chat2 sessions)."""
    storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
    storage_ns = config.get("storage_namespace") or "data"
    sp = StoragePaths(storage_root, storage_ns)
    storage = JsonFileStorage(sp)
    adapter = JfsChat2Primitives(storage)
    return Chat2Store(adapter)


def _make_prompt_entry(
    content: str,
    source: str,
    session_id: str,
    friendly_name: str,
    agent_name: str,
    utc_timestamp: str,
) -> Dict[str, Any]:
    """Create a standardized prompt entry with all required fields."""
    return {
        "text": content,
        "text_length": len(content),
        "source": source,
        "session_id": session_id,
        "friendly_name": friendly_name,
        "agent_name": agent_name,
        "utc_timestamp": utc_timestamp,
        "num_matching_docs": 0,
        "exclude": False,
    }


def extract_old_format(lucy_data_root: str, account: str) -> List[Dict[str, Any]]:
    """
    Extract user prompts from old-format chat files.

    Old format: data/chats/<account>/<uuid>.json
    Each file is a single JSON with 'messages' array.
    Each message has: role, content, utc_timestamp, metadata.
    """
    prompts: List[Dict[str, Any]] = []
    chats_dir = Path(lucy_data_root) / "data" / "chats" / account

    if not chats_dir.is_dir():
        logger.warning("Old-format chats dir not found: %s", chats_dir)
        return prompts

    json_files = sorted(chats_dir.glob("*.json"))
    logger.info("Scanning %d old-format sessions for account '%s'", len(json_files), account)

    for fpath in json_files:
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping unreadable file %s: %s", fpath.name, e)
            continue

        session_id = data.get("id", fpath.stem)
        friendly_name = data.get("friendly_name", "")
        agent_name = data.get("agent_name", "")

        for msg in data.get("messages", []):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").strip()
            if not content:
                continue

            prompts.append(_make_prompt_entry(
                content=content,
                source="old",
                session_id=session_id,
                friendly_name=friendly_name,
                agent_name=agent_name,
                utc_timestamp=msg.get("utc_timestamp", ""),
            ))

    logger.info("Extracted %d user prompts from old-format sessions", len(prompts))
    return prompts


def extract_new_format(store: Chat2Store, account: str) -> List[Dict[str, Any]]:
    """
    Extract user prompts from new-format (chat2) sessions.

    New format: data/chat2/sessions/<uuid>/meta.json + events.jsonl
    Events have: role, kind, payload, ts, actor.
    User messages have kind='user_message'.
    """
    prompts: List[Dict[str, Any]] = []
    sessions = store.list_sessions(account_name=account, limit=1000)

    logger.info("Scanning %d new-format sessions for account '%s'", len(sessions), account)

    for meta in sessions:
        try:
            events = list(store.stream_events(meta.session_id))
        except Exception as e:
            logger.warning("Skipping session %s: %s", meta.session_id, e)
            continue

        for evt in events:
            if evt.kind != "user_message":
                continue

            # payload can be a dict or str
            if isinstance(evt.payload, str):
                content = evt.payload.strip()
            else:
                content = evt.payload.get("content", "").strip()

            if not content:
                continue

            prompts.append(_make_prompt_entry(
                content=content,
                source="new",
                session_id=meta.session_id,
                friendly_name=meta.friendly_name,
                agent_name=meta.agent_name,
                utc_timestamp=evt.ts.isoformat(),
            ))

    logger.info("Extracted %d user prompts from new-format sessions", len(prompts))
    return prompts


def deduplicate(prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate by prompt text, keeping the first occurrence.

    Returns deduplicated list with a 'duplicate_of' field on duplicates
    (removed from final output but could be useful).
    """
    seen: Dict[str, int] = {}  # text -> index in unique list
    unique: List[Dict[str, Any]] = []

    for p in prompts:
        text = p["text"]
        if text in seen:
            # note which index this is a duplicate of
            p["duplicate_of_idx"] = seen[text]
            continue
        seen[text] = len(unique)
        unique.append(p)

    return unique


def _merge_with_existing(new_prompts: List[Dict[str, Any]], existing_corpus: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge new prompts with existing corpus entries, preserving num_matching_docs
    and exclude fields from existing entries where the text matches.
    """
    if not existing_corpus:
        return deduplicate(new_prompts)

    existing_prompts: List[Dict[str, Any]] = existing_corpus.get("prompts", [])
    # Build lookup by text
    existing_by_text: Dict[str, Dict[str, Any]] = {}
    for ep in existing_prompts:
        existing_by_text[ep["text"]] = ep

    merged: List[Dict[str, Any]] = []
    seen_texts: set = set()

    for p in new_prompts:
        if p["text"] in seen_texts:
            continue
        seen_texts.add(p["text"])

        if p["text"] in existing_by_text:
            # Preserve eval metadata from existing entry
            old = existing_by_text[p["text"]]
            p["num_matching_docs"] = old.get("num_matching_docs", 0)
            p["exclude"] = old.get("exclude", False)
        else:
            # New prompt — fresh defaults
            p["num_matching_docs"] = 0
            p["exclude"] = False

        merged.append(p)

    return merged


def build_corpus(
    lucy_data_root: str,
    store: Chat2Store,
    account: str,
    existing_corpus: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract and deduplicate prompts from both formats into a corpus."""
    old = extract_old_format(lucy_data_root, account)
    new = extract_new_format(store, account)

    all_prompts = old + new
    logger.info("Total raw prompts: %d (old: %d, new: %d)", len(all_prompts), len(old), len(new))

    unique = _merge_with_new(all_prompts, existing_corpus)
    logger.info("After merge+dedup: %d unique prompts", len(unique))

    # Stats: length distribution
    lengths = [p["text_length"] for p in unique]
    lengths_sorted = sorted(lengths)

    def pct(n: int) -> float:
        """nth percentile of lengths."""
        if not lengths_sorted:
            return 0
        idx = int(len(lengths_sorted) * n / 100)
        return lengths_sorted[min(idx, len(lengths_sorted) - 1)]

    return {
        "account": account,
        "total_prompts": len(unique),
        "source_counts": {
            "old_format": len(old),
            "new_format": len(new),
            "total_raw": len(all_prompts),
            "duplicates_removed": len(all_prompts) - len(unique),
        },
        "length_stats": {
            "min": lengths_sorted[0] if lengths_sorted else 0,
            "max": lengths_sorted[-1] if lengths_sorted else 0,
            "avg": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "p50": pct(50),
            "p90": pct(90),
            "p95": pct(95),
        },
        "prompts": unique,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a deduplicated corpus of user prompts from chat sessions.",
    )
    parser.add_argument(
        "--account",
        type=str,
        required=True,
        help="Account name (e.g. 'junwin').",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path relative to lucy_data_files root (default: data/eval/corpus.json).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s - %(message)s")

    config = ConfigManager("config.json")
    store = _build_store(config)

    external_roots = config.get("external_roots", {})
    lucy_data_root = external_roots.get("lucy_data_files", "/home/junwin/lucy_storage")

    # Try to load existing corpus to preserve metadata
    output_rel = args.output or "data/eval/corpus.json"
    output_path = Path(lucy_data_root) / output_rel
    existing_corpus = None
    if output_path.exists():
        try:
            existing_corpus = json.loads(output_path.read_text())
            logger.info("Loaded existing corpus (%d prompts) to preserve metadata.",
                         existing_corpus.get("total_prompts", 0))
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not load existing corpus; will create fresh.")

    corpus = build_corpus(
        lucy_data_root=lucy_data_root,
        store=store,
        account=args.account,
        existing_corpus=existing_corpus,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(corpus, indent=2, ensure_ascii=False))
    print(f"Corpus written to: {output_path}")
    print(f"Total unique prompts: {corpus['total_prompts']}")
    print(f"Length stats: min={corpus['length_stats']['min']}, "
          f"avg={corpus['length_stats']['avg']}, "
          f"max={corpus['length_stats']['max']}, "
          f"p50={corpus['length_stats']['p50']}, "
          f"p90={corpus['length_stats']['p90']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
