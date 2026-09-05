#!/usr/bin/env python3
"""Probe C — live document retrieval through the container PromptBuilder.

Issue #165 diagnostic: embeds the fixed query via the same singleton
PromptBuilder and _get_document_embedding_context call the /ask chain uses,
then prints each hit (source_id, score).

Exit 0 when >= 1 context is returned with score > 0.25; exits non-zero with a
clear message when no context passes or retrieval fails. First-hit identity is
printed for information (expected obsidian_importer.md) and is not a gate.

Run from the repo root:  ./.venv/bin/python scripts/check_embedding_retrieval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_manager import ConfigManager

QUERY = "What does the obsidian importer do and how does it create DocumentRef records?"
ACCOUNT_NAME = "junwin"
NAMESPACES = ["documents"]
TOP_K = 3
SCORE_THRESHOLD = 0.25
EXPECTED_FIRST_HIT = "obsidian_importer.md"


def main() -> int:
    config = ConfigManager("config.json")
    credential_path = config.get("credential_path") or ""
    print(f"credential_path: {credential_path}")
    print(f"embedding_store_backend: {config.get('embedding_store_backend') or '(unset)'}")
    print(f"query: {QUERY!r}")

    from src.container_config import container
    from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface

    prompt_builder = container.get(PromptBuilderInterface)
    contexts = prompt_builder._get_document_embedding_context(
        query=QUERY,
        account_name=ACCOUNT_NAME,
        namespaces=NAMESPACES,
        top_k=TOP_K,
    )

    print(f"document contexts: {len(contexts)}")
    for context in contexts:
        print(f"{context['source_id']} {context['score']:.3f}")

    if contexts:
        first = contexts[0]
        print(
            f"first hit: {first['source_id']} "
            f"(expected {EXPECTED_FIRST_HIT} — informational, not a gate)"
        )

    passing = [context for context in contexts if context["score"] > SCORE_THRESHOLD]
    if not passing:
        print(
            f"FAIL: no context scored above {SCORE_THRESHOLD} "
            f"(retrieval returned {len(contexts)} contexts)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAIL: retrieval failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
