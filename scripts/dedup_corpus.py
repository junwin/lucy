#!/usr/bin/env python3
"""
Deduplicate the prompt corpus by fuzzy-prefix matching.

Groups prompts whose first N characters are identical (default: 256) and
keeps only the first occurrence in each group. This removes near-duplicates
that differ only in their tails (e.g. a filename or minor rephrasing at the end).

The corpus is expected at: lucy_data_files/data/eval/corpus.json

Usage:
    # Show what would be removed (dry-run)
    python scripts/dedup_corpus.py --dry-run

    # Actually dedup
    python scripts/dedup_corpus.py

    # Custom prefix length
    python scripts/dedup_corpus.py --prefix-len 128

    # Show collision stats only
    python scripts/dedup_corpus.py --stats

    # List collision groups
    python scripts/dedup_corpus.py --list-groups
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_corpus(corpus_path: Path) -> Dict[str, Any]:
    """Load the prompt corpus JSON file."""
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus not found: {corpus_path}")
    with open(corpus_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None:
    """Write corpus back to disk atomically."""
    tmp = corpus_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)
    tmp.replace(corpus_path)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _find_collisions(
    prompts: List[Dict[str, Any]],
    prefix_len: int,
) -> Dict[str, List[int]]:
    """Group prompts by first *prefix_len* chars.

    Returns a dict mapping prefix -> list of indices in colliding groups
    (only for groups with 2 or more members).
    """
    prefix_map: Dict[str, List[int]] = defaultdict(list)
    for i, p in enumerate(prompts):
        prefix = p["text"][:prefix_len]
        prefix_map[prefix].append(i)

    return {k: v for k, v in prefix_map.items() if len(v) > 1}


def _deduplicate(
    prompts: List[Dict[str, Any]],
    prefix_len: int,
) -> tuple[List[Dict[str, Any]], int, int]:
    """Deduplicate by fuzzy prefix: keep first per group.

    Returns:
        (deduped_prompts, num_removed, num_groups)
    """
    collisions = _find_collisions(prompts, prefix_len)

    # Indices to drop: all but first in each colliding group
    drop_indices: set = set()
    for indices in collisions.values():
        drop_indices.update(indices[1:])  # keep indices[0], drop rest

    deduped = [p for i, p in enumerate(prompts) if i not in drop_indices]
    return deduped, len(drop_indices), len(collisions)


def _recompute_meta(corpus: Dict[str, Any]) -> None:
    """Update top-level stats after dedup."""
    prompts: List[Dict[str, Any]] = corpus["prompts"]
    corpus["total_prompts"] = len(prompts)

    # source_counts
    src: Counter = Counter()
    for p in prompts:
        src[p.get("source", "unknown")] += 1
    corpus["source_counts"] = dict(src)

    # length_stats
    lengths = sorted(p.get("text_length", 0) for p in prompts)
    if lengths:
        def _pct(n: int) -> float:
            idx = int(len(lengths) * n / 100)
            return lengths[min(idx, len(lengths) - 1)]

        corpus["length_stats"] = {
            "min": lengths[0],
            "max": lengths[-1],
            "avg": round(sum(lengths) / len(lengths), 1),
            "p50": _pct(50),
            "p90": _pct(90),
            "p95": _pct(95),
        }


def _print_stats(prompts: List[Dict[str, Any]], prefix_len: int) -> None:
    """Print pre-dedup collision stats."""
    collisions = _find_collisions(prompts, prefix_len)
    total_colliding = sum(len(v) for v in collisions.values())
    print(f"Total prompts:      {len(prompts)}")
    print(f"Prefix length:      {prefix_len}")
    print(f"Collision groups:   {len(collisions)}")
    print(f"Prompts in groups:  {total_colliding}")
    print(f"Removable:          {total_colliding - len(collisions)} (keep 1 per group)")
    print()

    # Histogram: group sizes
    size_counts = Counter(len(v) for v in collisions.values())
    print("Group size distribution:")
    for size, count in sorted(size_counts.items()):
        print(f"  {size:>2}-prompt groups: {count}")


def _list_groups(prompts: List[Dict[str, Any]], prefix_len: int, limit: int = 20) -> None:
    """Print collision groups with prompt texts."""
    collisions = _find_collisions(prompts, prefix_len)
    total = len(collisions)

    shown = min(limit, total)
    items = list(collisions.items())[:shown]

    print(f"{total} collision groups (showing first {shown}):\n")

    for gi, (prefix, indices) in enumerate(items):
        print(f"--- Group {gi + 1} ({len(indices)} prompts) ---")
        for idx in indices:
            t = prompts[idx]["text"]
            tail = t[prefix_len:] if len(t) > prefix_len else ""
            print(f"  [{idx}] len={len(t):>5}  "
                  f"text={t[:prefix_len]}"
                  f"{tail[:80] + '...' if len(tail) > 80 else tail}")
        print()

    if total > limit:
        print(f"... and {total - limit} more groups.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicate the prompt corpus by fuzzy-prefix matching.",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default="data/eval/corpus.json",
        help="Path to corpus JSON (relative to lucy_data_files root).",
    )
    parser.add_argument(
        "--prefix-len",
        type=int,
        default=256,
        help="Number of prefix characters to match for near-duplicate detection (default: 256).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without writing to disk.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Print collision statistics and exit.",
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        default=False,
        help="Print collision groups with prompt texts and exit.",
    )
    parser.add_argument(
        "--list-limit",
        type=int,
        default=20,
        help="Max groups to list (default: 20).",
    )
    args = parser.parse_args(argv)

    # Resolve corpus path
    corpus_path = Path("/home/junwin/lucy_storage") / args.corpus
    corpus = _load_corpus(corpus_path)
    prompts: List[Dict[str, Any]] = corpus["prompts"]

    # Read-only operations
    if args.stats:
        _print_stats(prompts, args.prefix_len)
        return 0

    if args.list_groups:
        _list_groups(prompts, args.prefix_len, limit=args.list_limit)
        return 0

    # --- Dedup ---
    before_count = len(prompts)

    deduped, removed, groups = _deduplicate(prompts, args.prefix_len)
    corpus["prompts"] = deduped
    _recompute_meta(corpus)

    after_count = len(deduped)

    print(f"Prefix length:   {args.prefix_len}")
    print(f"Collision groups: {groups}")
    print(f"Prompts before:  {before_count}")
    print(f"Prompts removed: {removed}")
    print(f"Prompts after:   {after_count}")
    print()

    if args.dry_run:
        print("[Dry-run] No changes written to disk.")
    else:
        _save_corpus(corpus_path, corpus)
        print(f"Corpus updated: {corpus_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
