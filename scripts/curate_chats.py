#!/usr/bin/env python3
"""CLI command to curate chat sessions — filter, summarize, or archive.

Wraps the curation library (CurationEngine) for batch or single-session use.

Usage examples:
    # Summarize a session by friendly name (preview only)
    python scripts/curate_chats.py --friendly-name "my-session" --account junwin --mode summarize

    # Summarize and publish digest
    python scripts/curate_chats.py --friendly-name "my-session" --account junwin --mode summarize --publish

    # Archive a session (summarize + move original + replace with digest)
    python scripts/curate_chats.py --session-id "uuid-here" --account junwin --mode archive --publish

    # Filter events from a session
    python scripts/curate_chats.py --friendly-name "my-session" --account junwin --mode filter \\
        --curation-rules '{"remove_kinds": ["tool_call", "tool_result"]}'

    # Batch: curate all sessions for an account (summarize mode, preview)
    python scripts/curate_chats.py --account junwin --mode summarize --batch

    # Batch with publish
    python scripts/curate_chats.py --account junwin --mode summarize --batch --publish

    # Dry-run (show what would be done without writing)
    python scripts/curate_chats.py --account junwin --mode summarize --batch --dry-run
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
from src.curation.core import CurationEngine
from src.llm.router_api import RouterApi
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build dependencies
# ---------------------------------------------------------------------------


def _build_store(config: ConfigManager) -> Chat2Store:
    """Construct a Chat2Store from config."""
    storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
    storage_ns = config.get("storage_namespace") or "data"
    sp = StoragePaths(storage_root, storage_ns)
    storage = JsonFileStorage(sp)
    adapter = JfsChat2Primitives(storage)
    return Chat2Store(adapter)


def _build_engine(config: ConfigManager) -> CurationEngine:
    """Build the curation engine with paths from config."""
    external_roots = config.get("external_roots", {})
    lucy_data_root = external_roots.get("lucy_data_files", "/home/junwin/lucy_storage")
    data_base = Path(lucy_data_root) / "data"
    llm_model = config.get("curation_llm_model", "gpt-4o-mini")

    store = _build_store(config)
    llm_api = RouterApi()

    return CurationEngine(
        chat2_store=store,
        llm_api=llm_api,
        llm_model=llm_model,
        digests_root=data_base / "digests",
        archives_root=data_base / "archives",
    )


# ---------------------------------------------------------------------------
# Batch curation
# ---------------------------------------------------------------------------


def _curate_all_sessions(
    engine: CurationEngine,
    store: Chat2Store,
    account: str,
    mode: str,
    preview: bool,
    publish: bool,
    template_name: str,
    curation_rules: Optional[Dict[str, Any]],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    """Curate all sessions for an account.

    Returns a list of result dicts, one per session.
    """
    sessions = store.list_sessions(account_name=account, limit=500)
    if not sessions:
        print(f"No sessions found for account '{account}'.")
        return []

    results: List[Dict[str, Any]] = []
    for s in sessions:
        sid = s.session_id
        fn = s.friendly_name or sid

        if dry_run:
            print(f"[DRY-RUN] Would curate: {fn} ({sid}) mode={mode}")
            results.append({
                "session_id": sid,
                "friendly_name": fn,
                "status": "dry-run",
            })
            continue

        print(f"Curating: {fn} ({sid}) ... ", end="", flush=True)
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
            results.append({
                "session_id": sid,
                "friendly_name": fn,
                "status": status,
                "output_path": result.get("output_path"),
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "session_id": sid,
                "friendly_name": fn,
                "status": "error",
                "error": str(e),
            })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Curate chat sessions — filter, summarize, or archive.",
    )

    # Session selection (mutually exclusive with --batch)
    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument(
        "--friendly-name",
        type=str,
        default=None,
        help="Friendly name of a single session to curate.",
    )
    session_group.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="UUID of a single session to curate.",
    )
    session_group.add_argument(
        "--batch",
        action="store_true",
        help="Curate all sessions for the given account.",
    )

    parser.add_argument(
        "--account",
        type=str,
        required=True,
        help="Account name (e.g. 'junwin').",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["filter", "summarize", "archive"],
        default="summarize",
        help="Curation mode (default: summarize).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        default=True,
        help="Return note_text without writing (default: true).",
    )
    parser.add_argument(
        "--no-preview",
        dest="preview",
        action="store_false",
        help="Disable preview (write changes).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=False,
        help="Write digest to data/digests/<account>/.",
    )
    parser.add_argument(
        "--template-name",
        type=str,
        default="default",
        help="Named template for digest formatting (default: 'default').",
    )
    parser.add_argument(
        "--curation-rules",
        type=str,
        default=None,
        help="JSON string of curation rules for filter mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without making changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )

    args = parser.parse_args(argv)

    # Logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s - %(message)s")

    # Validate: must have at least one selection method
    if not args.friendly_name and not args.session_id and not args.batch:
        parser.error("One of --friendly-name, --session-id, or --batch is required.")

    # Parse curation rules
    curation_rules: Optional[Dict[str, Any]] = None
    if args.curation_rules:
        try:
            curation_rules = json.loads(args.curation_rules)
        except json.JSONDecodeError as e:
            parser.error(f"Invalid --curation-rules JSON: {e}")

    # Build dependencies
    config = ConfigManager("config.json")
    engine = _build_engine(config)
    store = _build_store(config)

    # --- Batch mode ---
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

        # Summary
        total = len(results)
        ok_count = sum(1 for r in results if r.get("status") not in ("error", "dry-run"))
        error_count = sum(1 for r in results if r.get("status") == "error")
        dry_run_count = sum(1 for r in results if r.get("status") == "dry-run")

        print(f"\nDone. {total} sessions processed.")
        if ok_count:
            print(f"  OK: {ok_count}")
        if error_count:
            print(f"  Errors: {error_count}")
        if dry_run_count:
            print(f"  Dry-run: {dry_run_count}")

        return 1 if error_count else 0

    # --- Single session mode ---
    if args.dry_run:
        print(f"[DRY-RUN] Would curate: friendly_name={args.friendly_name} session_id={args.session_id} "
              f"account={args.account} mode={args.mode}")
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
