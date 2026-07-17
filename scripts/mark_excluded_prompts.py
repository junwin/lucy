#!/usr/bin/env python3
"""
Mark/unmark prompts in the corpus for exclusion from evaluation.

Supports rule-based exclusion (min length, max length, pattern), manual
operations (clear all, list excluded, show stats), and query mode to
extract prompts matching filters.

The corpus is expected at: lucy_data_files/data/eval/corpus.json

Usage:
    # Mark short prompts (< 32 chars) as excluded
    python scripts/mark_excluded_prompts.py --min-length 32

    # Mark long prompts (> 2000 chars) as excluded
    python scripts/mark_excluded_prompts.py --max-length 2000

    # Mark prompts matching a pattern
    python scripts/mark_excluded_prompts.py --pattern "^(hi|hello|ok|yes|no)\\b"

    # Combine rules
    python scripts/mark_excluded_prompts.py --min-length 32 --max-length 5000

    # Clear all exclude flags
    python scripts/mark_excluded_prompts.py --clear

    # Dry-run: preview what would change without writing
    python scripts/mark_excluded_prompts.py --min-length 32 --dry-run

    # Show stats only
    python scripts/mark_excluded_prompts.py --stats

    # List excluded prompts
    python scripts/mark_excluded_prompts.py --list-excluded

    # Query: first 20 included prompts with no matching docs
    python scripts/mark_excluded_prompts.py --query --query-limit 20

    # Query + save to file
    python scripts/mark_excluded_prompts.py --query --query-limit 50 --query-output /tmp/needs_docs.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_corpus(corpus_path: Path) -> Dict[str, Any]:
    """Load the prompt corpus JSON file."""
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus not found: {corpus_path}")
    with open(corpus_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None:
    """Write corpus back to disk."""
    tmp = corpus_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)
    tmp.replace(corpus_path)


def _ensure_fields(prompts: List[Dict[str, Any]]) -> int:
    """Add num_matching_docs and exclude fields to prompts that lack them.
    Returns number of prompts updated."""
    added = 0
    for p in prompts:
        if "num_matching_docs" not in p:
            p["num_matching_docs"] = 0
            added += 1
        if "exclude" not in p:
            p["exclude"] = False
    return added


def _print_stats(prompts: List[Dict[str, Any]]) -> None:
    """Print summary statistics about the corpus."""
    total = len(prompts)
    excluded = sum(1 for p in prompts if p.get("exclude", False))
    included = total - excluded
    have_docs = sum(1 for p in prompts if p.get("num_matching_docs", 0) > 0)
    no_docs = included - have_docs

    lengths = [p.get("text_length", 0) for p in prompts]
    ex_lengths = [p.get("text_length", 0) for p in prompts if p.get("exclude", False)]
    in_lengths = [p.get("text_length", 0) for p in prompts if not p.get("exclude", False)]

    def _avg(vals):
        return round(sum(vals) / len(vals), 1) if vals else 0

    print(f"Total prompts:       {total}")
    print(f"  Excluded:          {excluded} ({round(excluded/total*100, 1)}%)")
    print(f"  Included:          {included} ({round(included/total*100, 1)}%)")
    print(f"  Have docs:         {have_docs} ({round(have_docs/total*100, 1)}%)")
    print(f"  No docs (included):{no_docs}")
    print()
    print(f"Lengths (all):       min={min(lengths)}, max={max(lengths)}, avg={_avg(lengths)}")
    print(f"Lengths (excluded):  min={min(ex_lengths) if ex_lengths else 'N/A'}, "
          f"max={max(ex_lengths) if ex_lengths else 'N/A'}, "
          f"avg={_avg(ex_lengths)}")
    print(f"Lengths (included):  min={min(in_lengths) if in_lengths else 'N/A'}, "
          f"max={max(in_lengths) if in_lengths else 'N/A'}, "
          f"avg={_avg(in_lengths)}")


def _list_excluded(prompts: List[Dict[str, Any]], limit: int = 50) -> None:
    """Print the first N excluded prompts."""
    excluded = [p for p in prompts if p.get("exclude", False)]
    print(f"{len(excluded)} excluded prompts (showing first {min(limit, len(excluded))}):\n")
    for i, p in enumerate(excluded[:limit]):
        text = p["text"].replace("\n", "\\n")
        if len(text) > 120:
            text = text[:117] + "..."
        print(f"  [{i}] len={p.get('text_length', 0):>5}  docs={p.get('num_matching_docs', 0):>2}  "
              f"\"{text}\"")
    if len(excluded) > limit:
        print(f"  ... and {len(excluded) - limit} more.")


def _query_prompts(
    prompts: List[Dict[str, Any]],
    *,
    limit: int = 50,
    output_path: Optional[str] = None,
    max_docs: int = 0,
    max_length: Optional[int] = None,
) -> None:
    """Query: find included prompts where num_matching_docs <= max_docs
    and optionally text_length < max_length.

    Prints a summary table and optionally writes a JSON subset.
    Each output record gets an explicit 'index' field numbered 0,1,2,...

    Args:
        prompts: List of prompt dicts.
        limit: Max number of matches to show/save.
        output_path: If set, write matching prompts to this JSON file.
        max_docs: Only match prompts with num_matching_docs <= this value.
        max_length: If set, only match prompts with text_length < this value.
    """
    matches = [
        p for p in prompts
        if not p.get("exclude", False)
        and p.get("num_matching_docs", 0) <= max_docs
    ]
    if max_length is not None:
        matches = [p for p in matches if p.get("text_length", 0) < max_length]

    total_matches = len(matches)
    shown = min(limit, total_matches)
    subset = matches[:shown]

    filters = [f"exclude=false", f"num_matching_docs <= {max_docs}"]
    if max_length is not None:
        filters.append(f"text_length < {max_length}")
    print(f"Filter: {', '.join(filters)}")
    print(f"Found:  {total_matches} matching prompts (showing first {shown}):\n")

    for i, p in enumerate(subset):
        text = p["text"].replace("\n", "\\n")
        if len(text) > 140:
            text = text[:137] + "..."
        print(f"  [{i}] len={p.get('text_length', 0):>5}  docs={p.get('num_matching_docs', 0):>2}  "
              f"\"{text}\"")

    if total_matches > limit:
        print(f"  ... and {total_matches - limit} more.")

    if output_path:
        # Build output records with explicit index
        output = [
            {"index": i, **p}
            for i, p in enumerate(subset)
        ]
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(output)} prompts to: {out}")


def _apply_rules(
    prompts: List[Dict[str, Any]],
    *,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
) -> int:
    """Apply exclusion rules. Returns number of prompts newly excluded."""
    compiled = re.compile(pattern, re.IGNORECASE) if pattern else None
    count = 0

    for p in prompts:
        if p.get("exclude", False):
            continue  # already excluded

        exclude = False
        if min_length is not None and p.get("text_length", 0) < min_length:
            exclude = True
        if max_length is not None and p.get("text_length", 0) > max_length:
            exclude = True
        if compiled is not None and compiled.search(p.get("text", "")):
            exclude = True

        if exclude:
            p["exclude"] = True
            count += 1

    return count


def _clear_excludes(prompts: List[Dict[str, Any]]) -> int:
    """Clear all exclude flags. Returns number cleared."""
    count = 0
    for p in prompts:
        if p.get("exclude", False):
            p["exclude"] = False
            count += 1
    return count


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mark/unmark prompts in the corpus for exclusion from evaluation.",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default="data/eval/corpus.json",
        help="Path to corpus JSON (relative to lucy_data_files root).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=None,
        help="Exclude prompts shorter than this many characters.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=None,
        help="Exclude prompts longer than this many characters.",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        help="Regex pattern; prompts whose text matches are excluded (case-insensitive).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="Clear all exclude flags (reset to included).",
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
        help="Print corpus statistics and exit.",
    )
    parser.add_argument(
        "--list-excluded",
        action="store_true",
        default=False,
        help="List excluded prompts and exit.",
    )
    parser.add_argument(
        "--list-limit",
        type=int,
        default=50,
        help="Max excluded prompts to list (default: 50).",
    )
    # Query mode
    parser.add_argument(
        "--query",
        action="store_true",
        default=False,
        help="Query included prompts with no matching docs (or --query-max-docs).",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=50,
        help="Max results to return in query mode (default: 50).",
    )
    parser.add_argument(
        "--query-output",
        type=str,
        default=None,
        help="When set, write query results to this JSON file.",
    )
    parser.add_argument(
        "--query-max-docs",
        type=int,
        default=0,
        help="Match prompts with num_matching_docs <= this value (default: 0).",
    )
    parser.add_argument(
        "--query-max-length",
        type=int,
        default=None,
        help="Match only prompts with text_length < this value.",
    )
    args = parser.parse_args(argv)

    # Resolve corpus path
    corpus_path = Path("/home/junwin/lucy_storage") / args.corpus
    corpus = _load_corpus(corpus_path)
    prompts: List[Dict[str, Any]] = corpus["prompts"]

    # Ensure all prompts have the new fields
    field_adds = _ensure_fields(prompts)
    if field_adds:
        print(f"Added missing fields to {field_adds} prompts.")

    # Read-only operations
    if args.stats:
        _print_stats(prompts)
        return 0

    if args.list_excluded:
        _list_excluded(prompts, limit=args.list_limit)
        return 0

    if args.query:
        _query_prompts(
            prompts,
            limit=args.query_limit,
            output_path=args.query_output,
            max_docs=args.query_max_docs,
            max_length=args.query_max_length,
        )
        return 0

    # Determine action
    has_rules = args.min_length is not None or args.max_length is not None or args.pattern is not None

    if not has_rules and not args.clear:
        parser.print_help()
        print("\nError: specify at least one rule (--min-length, --max-length, --pattern) or --clear or --stats.")
        return 1

    before_excluded = sum(1 for p in prompts if p.get("exclude", False))

    # Mutate
    if args.clear:
        cleared = _clear_excludes(prompts)
        print(f"Cleared exclude flag on {cleared} prompts.")
    elif has_rules:
        newly_excluded = _apply_rules(
            prompts,
            min_length=args.min_length,
            max_length=args.max_length,
            pattern=args.pattern,
        )
        print(f"Excluded {newly_excluded} additional prompts.")

    after_excluded = sum(1 for p in prompts if p.get("exclude", False))
    total = len(prompts)

    print(f"\nBefore: {before_excluded}/{total} excluded ({round(before_excluded/total*100,1)}%)")
    print(f"After:  {after_excluded}/{total} excluded ({round(after_excluded/total*100,1)}%)")

    if args.dry_run:
        print("\n[Dry-run] No changes written to disk.")
    else:
        _save_corpus(corpus_path, corpus)
        print(f"\nCorpus updated: {corpus_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
