#!/usr/bin/env python3
"""CLI command to curate chat sessions — filter, summarize, or archive."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.coala_memory.episodic import EpisodicMemoryManager, EpisodicSessionQuery
from src.curation.container_factory import get_curation_engine
from src.curation.core import CurationEngine

logger = logging.getLogger(__name__)


def _get_episodic_store() -> EpisodicMemoryManager:
    from src.container_config import container

    if container is None:
        raise RuntimeError("dependency injection container is not configured")
    return container.get(EpisodicMemoryManager)


def _curate_all_sessions(
    engine: CurationEngine,
    store: EpisodicMemoryManager,
    account: str,
    mode: str,
    preview: bool,
    publish: bool,
    template_name: str,
    curation_rules: Optional[Dict[str, Any]],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    sessions = store.list_sessions(
        EpisodicSessionQuery(account_name=account, limit=500)
    )
    if not sessions:
        print(f"No sessions found for account '{account}'.")
        return []

    results: List[Dict[str, Any]] = []
    for session in sessions:
        sid = session.session_id
        friendly_name = session.friendly_name or sid

        if dry_run:
            print(f"[DRY-RUN] Would curate: {friendly_name} ({sid}) mode={mode}")
            results.append(
                {
                    "session_id": sid,
                    "friendly_name": friendly_name,
                    "status": "dry-run",
                }
            )
            continue

        print(f"Curating: {friendly_name} ({sid}) ... ", end="", flush=True)
        try:
            result = engine.curate(
                session_id=sid,
                account=account,
                mode=mode,
                preview=preview,
                publish=publish,
                template_name=template_name,
                curation_rules=curation_rules,
            )
            status = result.get("status", "error")
            print(status)
            results.append(
                {
                    "session_id": sid,
                    "friendly_name": friendly_name,
                    "status": status,
                    "output_path": result.get("output_path"),
                }
            )
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append(
                {
                    "session_id": sid,
                    "friendly_name": friendly_name,
                    "status": "error",
                    "error": str(exc),
                }
            )

    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Curate chat sessions — filter, summarize, or archive."
    )

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--friendly-name", type=str, default=None)
    selection.add_argument("--session-id", type=str, default=None)
    selection.add_argument("--batch", action="store_true")

    parser.add_argument("--account", type=str, required=True)
    parser.add_argument(
        "--mode",
        choices=["filter", "summarize", "archive"],
        default="summarize",
    )
    parser.add_argument("--preview", action="store_true", default=True)
    parser.add_argument("--no-preview", dest="preview", action="store_false")
    parser.add_argument("--publish", action="store_true", default=False)
    parser.add_argument("--template-name", type=str, default="default")
    parser.add_argument("--curation-rules", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s - %(message)s",
    )

    if not args.friendly_name and not args.session_id and not args.batch:
        parser.error("One of --friendly-name, --session-id, or --batch is required.")

    curation_rules: Optional[Dict[str, Any]] = None
    if args.curation_rules:
        try:
            curation_rules = json.loads(args.curation_rules)
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid --curation-rules JSON: {exc}")

    engine = get_curation_engine()
    store = _get_episodic_store()

    if args.batch:
        results = _curate_all_sessions(
            engine=engine,
            store=store,
            account=args.account,
            mode=args.mode,
            preview=args.preview,
            publish=args.publish,
            template_name=args.template_name,
            curation_rules=curation_rules,
            dry_run=args.dry_run,
        )
        total = len(results)
        ok_count = sum(
            1 for result in results if result.get("status") not in ("error", "dry-run")
        )
        error_count = sum(1 for result in results if result.get("status") == "error")
        dry_run_count = sum(
            1 for result in results if result.get("status") == "dry-run"
        )
        print(f"\nDone. {total} sessions processed.")
        if ok_count:
            print(f"  OK: {ok_count}")
        if error_count:
            print(f"  Errors: {error_count}")
        if dry_run_count:
            print(f"  Dry-run: {dry_run_count}")
        return 1 if error_count else 0

    if args.dry_run:
        print(
            f"[DRY-RUN] Would curate: friendly_name={args.friendly_name} "
            f"session_id={args.session_id} account={args.account} mode={args.mode}"
        )
        return 0

    result = engine.curate(
        session_id=args.session_id,
        friendly_name=args.friendly_name,
        account=args.account,
        mode=args.mode,
        preview=args.preview,
        publish=args.publish,
        template_name=args.template_name,
        curation_rules=curation_rules,
    )

    status = result.get("status", "error")
    print(f"Status: {status}")
    if result.get("note_text"):
        print("\n--- Digest ---")
        print(result["note_text"])
    if result.get("output_path"):
        print(f"\nOutput: {result['output_path']}")
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
