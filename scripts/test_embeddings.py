#!/usr/bin/env python3
"""Test embeddings: compare a source string against test strings.

Usage:
    python scripts/test_embeddings.py --source "hello" --tests "hi" "hey" "goodbye"
    python scripts/test_embeddings.py --source "hello" --tests-file tests.txt
    python scripts/test_embeddings.py --source "hello" --tests "hi" --model mistral-embed

Output: JSON array of {index, text, score}, sorted best match first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.embeddings import EmbeddingFacade


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test embedding similarity")
    parser.add_argument("--source", required=True, help="Source string to compare against")
    parser.add_argument(
        "--tests", nargs="*", default=[], help="Test strings (as positional args)"
    )
    parser.add_argument(
        "--tests-file",
        default=None,
        help="File with one test string per line",
    )
    parser.add_argument(
        "--model",
        default="text-embedding-3-small",
        help="Embedding model (default: text-embedding-3-small)",
    )
    parser.add_argument(
        "--metric",
        default="cosine",
        choices=["cosine", "euclidean", "dot_product"],
        help="Distance metric (default: cosine)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw JSON only (no banner)",
    )
    return parser.parse_args()


def load_tests(args: argparse.Namespace) -> list[str]:
    """Collect test strings from --tests and/or --tests-file."""
    tests: list[str] = list(args.tests)
    if args.tests_file:
        path = Path(args.tests_file)
        if not path.exists():
            print(f"ERROR: tests-file not found: {path}", file=sys.stderr)
            sys.exit(1)
        tests.extend(line.strip() for line in path.read_text().splitlines() if line.strip())
    if not tests:
        print("ERROR: No test strings provided. Use --tests or --tests-file.", file=sys.stderr)
        sys.exit(1)
    return tests


def main() -> None:
    args = parse_args()
    tests = load_tests(args)

    facade = EmbeddingFacade()

    if not args.raw:
        print(f"Model: {args.model}  |  Metric: {args.metric}")
        print(f"Source: {args.source!r}")
        print(f"Tests:  {len(tests)} strings")
        print("-" * 50)

    # 1. Embed source
    source_resp = facade.embed([args.source], model=args.model)
    source_vec = source_resp.embeddings[0]

    # 2. Batch-embed all test strings (single API call)
    test_resp = facade.embed(tests, model=args.model)
    test_vecs = test_resp.embeddings

    # 3. Compare each test against source
    from src.embeddings.comparison import DistanceMetric, _score

    metric = DistanceMetric(args.metric)

    results: list[dict] = []
    for i, (text, vec) in enumerate(zip(tests, test_vecs)):
        score = _score(source_vec, vec, metric)
        results.append({"index": i, "text": text, "score": round(score, 6)})

    # Sort best first
    results.sort(key=lambda r: r["score"], reverse=True)

    # 4. Output
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
