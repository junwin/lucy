#!/usr/bin/env python3
"""
Evaluate the document enrichment pipeline against the prompt corpus.

Runs get_document_context_traced() for every prompt (or a sample) and
captures per-prompt metrics plus aggregate statistics.

After evaluation, writes num_matching_docs back to each prompt in the corpus,
so the corpus tracks which prompts matched documents.

Prompts marked "exclude": true in the corpus are skipped.

Summary is printed to stdout as JSON (aggregate only — no per-prompt data).
The corpus file is updated in-place with per-prompt num_matching_docs.

Usage:
    # Full run (only non-excluded prompts) — summary to stdout
    python scripts/eval_enrichment.py --account junwin --corpus corpus.json

    # Also write the full report (including per-prompt details) to a file
    python scripts/eval_enrichment.py --account junwin --corpus corpus.json --output report.json

    # Full run including excluded prompts
    python scripts/eval_enrichment.py --account junwin --include-excluded

    # Quick sample
    python scripts/eval_enrichment.py --account junwin --sample 50

    # Sample with specific kind filter
    python scripts/eval_enrichment.py --account junwin --sample 100 --kind obsidian_note

    # No kind filter (search all documents)
    python scripts/eval_enrichment.py --account junwin --sample 50 --kind ''

    # Dry-run: don't write num_matching_docs back to corpus
    python scripts/eval_enrichment.py --account junwin --no-writeback
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root on sys.path
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.config_manager import ConfigManager
from src.keywords.keywords import Keywords
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from src.utils.document_context import get_document_context_traced

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_corpus(corpus_path: Path) -> Dict[str, Any]:
    """Load the prompt corpus JSON file.

    Accepts both the original format (with top-level ``total_prompts``,
    ``source_counts``, ``length_stats``) and the simpler format containing
    only ``{"prompts": [...]}``.
    """
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus not found: {corpus_path}")
    with open(corpus_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_corpus_meta(corpus: Dict[str, Any]) -> None:
    """Fill in missing top-level corpus fields computed from the prompts array.

    Mutates *corpus* in-place so that callers can rely on ``total_prompts``,
    ``source_counts``, and ``length_stats`` always being present.
    """
    prompts: List[Dict[str, Any]] = corpus.get("prompts", [])

    if "total_prompts" not in corpus:
        corpus["total_prompts"] = len(prompts)

    if "source_counts" not in corpus:
        src: Counter = Counter()
        for p in prompts:
            src[p.get("source", "unknown")] += 1
        corpus["source_counts"] = dict(src)

    if "length_stats" not in corpus:
        lengths = sorted(p.get("text_length", 0) for p in prompts)
        if lengths:
            corpus["length_stats"] = {
                "count": len(lengths),
                "min": lengths[0],
                "max": lengths[-1],
                "mean": round(sum(lengths) / len(lengths), 1),
                "p50": lengths[len(lengths) // 2],
                "p90": lengths[int(len(lengths) * 0.9)],
                "p95": lengths[int(len(lengths) * 0.95)],
            }
        else:
            corpus["length_stats"] = {}


def _save_corpus(corpus_path: Path, corpus: Dict[str, Any]) -> None:
    """Write corpus back to disk atomically (per-prompt updates only, no summary)."""
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


def _build_storage(config: ConfigManager) -> JsonFileStorage:
    """Build a JsonFileStorage from config."""
    storage_root = config.get("storage_root_path") or "/home/junwin/lucy_storage"
    storage_ns = config.get("storage_namespace") or "data"
    sp = StoragePaths(storage_root, storage_ns)
    return JsonFileStorage(sp)


def _evaluate_one(
    storage: JsonFileStorage,
    account_name: str,
    prompt: Dict[str, Any],
    prompt_index: int,
    kind: Optional[str],
    docs_tag: Optional[str],
    limit: int,
    max_chars: int,
    keywords: Keywords,
) -> Dict[str, Any]:
    """Run traced enrichment for a single prompt and return per-prompt metrics."""
    t0 = time.perf_counter()
    error: Optional[str] = None
    trace: Dict[str, Any] = {}
    contexts: List[Dict[str, Any]] = []

    try:
        contexts, trace = get_document_context_traced(
            storage=storage,
            account_name=account_name,
            query=prompt["text"],
            kind=kind,
            docs_tag=docs_tag,
            limit=limit,
            max_chars=max_chars,
            keywords=keywords,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # --- Derive per-prompt metrics from trace ---
    candidates = trace.get("candidates", [])
    selected = trace.get("selected", [])
    query_keywords = trace.get("query_keywords", [])

    num_candidates = len(candidates)
    num_scored = sum(1 for c in candidates if c.get("score", 0) > 0)
    num_selected = len(selected)

    scores = [s.get("score", 0) for s in selected]
    max_score = max(scores) if scores else 0
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Distinct matched terms across all selected docs
    all_matched: List[str] = []
    for s in selected:
        all_matched.extend(s.get("matched_terms", []))
    distinct_matched = sorted(set(all_matched))

    snippet_total_chars = sum(s.get("snippet_len", 0) for s in selected)
    num_truncated = sum(1 for s in selected if s.get("truncated", False))

    # Score distribution across all candidates (0, 1, 2, ...)
    score_dist = Counter(c.get("score", 0) for c in candidates)

    return {
        "prompt_index": prompt_index,
        "prompt_text": prompt["text"],
        "prompt_length": prompt["text_length"],
        "source": prompt.get("source", ""),
        "session_id": prompt.get("session_id", ""),
        "friendly_name": prompt.get("friendly_name", ""),
        "agent_name": prompt.get("agent_name", ""),
        "query_keywords": query_keywords,
        "num_query_keywords": len(query_keywords),
        "num_candidates": num_candidates,
        "num_scored": num_scored,
        "num_selected": num_selected,
        "max_score": max_score,
        "avg_score": avg_score,
        "distinct_matched_terms": distinct_matched,
        "num_distinct_matched": len(distinct_matched),
        "snippet_total_chars": snippet_total_chars,
        "num_truncated": num_truncated,
        "score_distribution": dict(sorted(score_dist.items())),
        "empty": num_selected == 0,
        "zero_score": num_scored == 0,
        "elapsed_ms": elapsed_ms,
        "error": error,
    }


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics from per-prompt results."""
    total = len(results)
    errors = [r for r in results if r["error"]]
    ok = [r for r in results if not r["error"]]

    if not ok:
        return {"total_prompts": total, "total_errors": len(errors), "error": "no successful results"}

    # Hit rate: % that got at least one selected context
    hits = sum(1 for r in ok if not r["empty"])
    hit_rate = round(hits / len(ok) * 100, 1)

    # Zero-score rate: % where no candidate had score > 0
    zero_scores = sum(1 for r in ok if r["zero_score"])
    zero_rate = round(zero_scores / len(ok) * 100, 1)

    # Selected distribution
    selected_dist = Counter(r["num_selected"] for r in ok)

    # Score distribution across all candidates
    global_score_dist: Counter = Counter()
    for r in ok:
        global_score_dist.update(r.get("score_distribution", {}))

    # Matched terms frequency across all prompts
    term_freq: Counter = Counter()
    for r in ok:
        for term in r.get("distinct_matched_terms", []):
            term_freq[term] += 1

    # Timing
    times = sorted(r["elapsed_ms"] for r in ok)

    def _pct(vals: List[float], n: int) -> float:
        if not vals:
            return 0.0
        idx = int(len(vals) * n / 100)
        return vals[min(idx, len(vals) - 1)]

    # Numeric averages
    nums = {
        "num_candidates": [r["num_candidates"] for r in ok],
        "num_scored": [r["num_scored"] for r in ok],
        "num_selected": [r["num_selected"] for r in ok],
        "max_score": [r["max_score"] for r in ok],
        "avg_score": [r["avg_score"] for r in ok],
        "num_distinct_matched": [r["num_distinct_matched"] for r in ok],
        "snippet_total_chars": [r["snippet_total_chars"] for r in ok],
        "num_truncated": [r["num_truncated"] for r in ok],
        "num_query_keywords": [r["num_query_keywords"] for r in ok],
    }

    avgs = {}
    for key, vals in nums.items():
        avgs[key] = {
            "mean": round(sum(vals) / len(vals), 2) if vals else 0,
            "min": min(vals) if vals else 0,
            "max": max(vals) if vals else 0,
        }

    # Context recall: how many chars of context did we retrieve on average?
    snippet_chars = nums["snippet_total_chars"]
    total_snippet_chars = sum(snippet_chars)

    return {
        "total_prompts": total,
        "total_errors": len(errors),
        "total_successful": len(ok),
        "hit_rate_pct": hit_rate,
        "zero_score_rate_pct": zero_rate,
        "selected_distribution": {str(k): v for k, v in sorted(selected_dist.items())},
        "global_score_distribution": {str(k): v for k, v in sorted(global_score_dist.items())},
        "top_matched_terms": term_freq.most_common(30),
        "timing_ms": {
            "min": times[0] if times else 0,
            "max": times[-1] if times else 0,
            "avg": round(sum(times) / len(times), 1) if times else 0,
            "p50": _pct(times, 50),
            "p90": _pct(times, 90),
            "p95": _pct(times, 95),
        },
        "averages": avgs,
        "total_snippet_chars_retrieved": total_snippet_chars,
        "avg_chars_per_prompt": round(total_snippet_chars / len(ok), 1) if ok else 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the document enrichment pipeline against the prompt corpus.",
    )
    parser.add_argument("--account", type=str, required=True, help="Account name (e.g. 'junwin').")
    parser.add_argument(
        "--corpus",
        type=str,
        default="data/eval/corpus.json",
        help="Path to corpus JSON (relative to lucy_data_files root).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional path for full report JSON (relative to lucy_data_files root). "
             "When omitted the summary is printed to stdout only.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Evaluate only N prompts (0 = all).",
    )
    parser.add_argument(
        "--kind",
        type=str,
        default="obsidian_note",
        help="Document kind filter (default: obsidian_note). Use '' for no filter.",
    )
    parser.add_argument(
        "--docs-tag",
        type=str,
        default=None,
        help="Document tag filter (default: None = no tag filter).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Max documents to return per prompt (default: 3).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Max chars per snippet (default: 6000).",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    parser.add_argument(
        "--no-writeback",
        action="store_true",
        default=False,
        help="Do not write num_matching_docs back to the corpus.",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        default=False,
        help="Evaluate ALL prompts, even those marked exclude: true.",
    )
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s - %(message)s")

    # --- Load config and build storage ---
    config = ConfigManager("config.json")
    storage = _build_storage(config)

    external_roots = config.get("external_roots", {})
    lucy_data_root = external_roots.get("lucy_data_files", "/home/junwin/lucy_storage")

    # --- Load corpus ---
    corpus_path = Path(lucy_data_root) / args.corpus
    corpus = _load_corpus(corpus_path)
    _compute_corpus_meta(corpus)

    all_prompts: List[Dict[str, Any]] = corpus["prompts"]

    # Ensure new fields exist on all prompts
    field_adds = _ensure_fields(all_prompts)
    if field_adds:
        logger.info("Added missing fields to %d prompts.", field_adds)

    # --- Filter out excluded prompts ---
    if args.include_excluded:
        eval_prompts = all_prompts
        num_skipped = 0
    else:
        eval_prompts = [p for p in all_prompts if not p.get("exclude", False)]
        num_skipped = len(all_prompts) - len(eval_prompts)

    if num_skipped:
        logger.info("Skipping %d excluded prompts (%d remaining).",
                     num_skipped, len(eval_prompts))

    # --- Apply sample limit ---
    if args.sample and args.sample < len(eval_prompts):
        eval_prompts = eval_prompts[: args.sample]
        logger.info("Sampling %d of %d prompts", args.sample, len(eval_prompts))
    else:
        logger.info("Evaluating %d prompts", len(eval_prompts))

    # Normalize kind: '' means no filter
    kind: Optional[str] = args.kind if args.kind else None

    logger.info("Params: kind=%r, docs_tag=%r, limit=%d, max_chars=%d",
                 kind, args.docs_tag, args.limit, args.max_chars)

    # --- Create a single Keywords instance for the whole run ---
    logger.info("Loading spaCy + NLTK (one-time)...")
    keywords = Keywords()

    # --- Evaluate ---
    results: List[Dict[str, Any]] = []
    t_start = time.perf_counter()

    for i, prompt in enumerate(eval_prompts):
        if (i + 1) % 100 == 0:
            elapsed = time.perf_counter() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info("Progress: %d/%d (%.1f prompts/s)", i + 1, len(eval_prompts), rate)

        result = _evaluate_one(
            storage=storage,
            account_name=args.account,
            prompt=prompt,
            prompt_index=i,
            kind=kind,
            docs_tag=args.docs_tag,
            limit=args.limit,
            max_chars=args.max_chars,
            keywords=keywords,
        )
        results.append(result)

        # Update the corpus entry with matching docs count (in-place, same object)
        prompt["num_matching_docs"] = result["num_selected"]

    total_elapsed = round(time.perf_counter() - t_start, 1)
    logger.info("Evaluation complete in %.1fs", total_elapsed)

    # --- Write back num_matching_docs to corpus (per-prompt only, no summary) ---
    if not args.no_writeback:
        _save_corpus(corpus_path, corpus)
        logger.info("Wrote num_matching_docs back to corpus: %s", corpus_path)

    # --- Aggregate ---
    aggregate = _aggregate(results)
    aggregate["params"] = {
        "account": args.account,
        "kind": args.kind,
        "docs_tag": args.docs_tag,
        "limit": args.limit,
        "max_chars": args.max_chars,
        "sample": args.sample,
        "include_excluded": args.include_excluded,
        "prompts_skipped_excluded": num_skipped,
    }
    aggregate["total_elapsed_sec"] = total_elapsed

    # --- Build summary (aggregate only — per_prompt omitted to keep stdout small) ---
    summary = {
        "corpus_summary": {
            "total_prompts_in_corpus": corpus["total_prompts"],
            "total_excluded": sum(1 for p in all_prompts if p.get("exclude", False)),
            "prompts_evaluated": len(eval_prompts),
            "prompts_skipped_excluded": num_skipped,
            "source_counts": corpus.get("source_counts", {}),
            "length_stats": corpus.get("length_stats", {}),
        },
        "aggregate": aggregate,
    }

    # --- Output: summary to stdout (aggregate only — small) ---
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # --- Optionally write full report (including per_prompt) to file ---
    if args.output:
        # Build full report with per_prompt data
        full_report = {**summary, "per_prompt": results}
        output_path = Path(lucy_data_root) / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)
        print(f"\nFull report (with per_prompt details) written to: {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
