#!/usr/bin/env python3
"""
Extract a deduplicated corpus of user prompts from all chat sessions.

Reads the configured relational episodic database through galet-memory.

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

from galet_memory import EpisodicMemoryManager, EpisodicSessionQuery, SqliteEpisodicMemory
from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def _build_store(config: ConfigManager) -> SqliteEpisodicMemory:
    storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
    storage_ns = config.get("storage_namespace") or "data"
    path = Path(config.get("episodic_memory_db_path") or
                Path(storage_root) / storage_ns / "chat2.sqlite")
    if not path.is_file():
        raise FileNotFoundError(path)
    return SqliteEpisodicMemory(path, initialize_schema=False)


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


def extract_prompts(store: EpisodicMemoryManager, account: str) -> List[Dict[str, Any]]:
    """Extract user prompts through the supported episodic interface."""
    prompts = []
    sessions = store.list_sessions(EpisodicSessionQuery(account_name=account, limit=1000))
    for meta in sessions:
        session = store.get_session(meta.session_id, event_scope="all")
        if session is None:
            continue
        for event in session.events:
            if event.kind != "user_message" or not isinstance(event.content, str):
                continue
            content = event.content.strip()
            if content:
                prompts.append(_make_prompt_entry(
                    content=content, source="episodic", session_id=meta.session_id,
                    friendly_name=meta.friendly_name or "", agent_name=meta.agent_name,
                    utc_timestamp=event.created_at.isoformat() if event.created_at else "",
                ))
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
    store: EpisodicMemoryManager,
    account: str,
    existing_corpus: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract and deduplicate prompts from current episodic storage."""
    all_prompts = extract_prompts(store, account)
    logger.info("Total raw prompts: %d", len(all_prompts))

    unique = _merge_with_existing(all_prompts, existing_corpus)
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
            "episodic": len(all_prompts),
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

    try:
        corpus = build_corpus(store=store, account=args.account, existing_corpus=existing_corpus)
    finally:
        store.close()

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
