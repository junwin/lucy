#!/usr/bin/env python3
"""Batch-embed existing chat digests into the embedding store.

Usage:
    python scripts/embed_digests.py --dry-run
    python scripts/embed_digests.py
    python scripts/embed_digests.py --account junwin --model text-embedding-3-small
    python scripts/embed_digests.py --summarize   # opt-in: re-summarize before embedding
    python scripts/embed_digests.py --force --summarize  # force re-embed with summaries
    python scripts/embed_digests.py --recursive   # scan subdirectories
    python scripts/embed_digests.py --files path/to/d1.md,path/to/d2.md  # explicit files
    python scripts/embed_digests.py --files /abs/path/d1.md,/abs/path/d2.md

Reads .md digest files from <lucy_data_root>/data/digests/<account>/,
embeds the digest text directly (digests are already summaries), and persists
as EmbeddingRecord via JsonFileStorage. Skips files that already have a
matching embedding record (idempotent).

Pass --summarize to re-summarize via LLM before embedding (not recommended —
digests are already summaries; double-summarization loses detail).

If config.json has test paths (e.g. /tmp/pytest-*), use --lucy-data-root
and --storage-root to override.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_manager import ConfigManager
from src.embeddings.facade import EmbeddingFacade
from galet.router_api import RouterApi
from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import EmbeddingRecord
from src.storage_paths.storage_paths import StoragePaths

logging.basicConfig(level=logging.WARNING)

# Known production defaults (used when config.json has test paths)
PROD_LUCY_DATA_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_NS = "data"

# ---------------------------------------------------------------------------
# Summarization prompt
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a concise summarizer. Your job is to distill a chat session digest "
    "into a short, searchable summary. Preserve: key topics, decisions made, "
    "files modified, commands run, and open questions. Drop boilerplate, "
    "truncated notes, and empty sections. Output plain text — no Markdown formatting."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-embed chat digests")
    parser.add_argument(
        "--account", default="junwin", help="Account name (default: junwin)"
    )
    parser.add_argument(
        "--model",
        default="text-embedding-3-small",
        help="Embedding model (default: text-embedding-3-small)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only — do not embed or persist",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed even if a record already exists",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=100,
        help="Minimum character count to embed (default: 100)",
    )
    parser.add_argument(
        "--lucy-data-root",
        default=None,
        help="Override lucy_data_files root (digests live under <root>/data/digests/)",
    )
    parser.add_argument(
        "--storage-root",
        default=None,
        help="Override storage_root_path (embeddings persisted under <root>/data/embeddings/)",
    )
    # --- File selection flags ---
    parser.add_argument(
        "--files",
        default=None,
        help="Comma-separated list of specific digest file paths "
        "(absolute, or relative to the digests directory). "
        "When set, --recursive is ignored.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        default=False,
        help="Recursively scan digest directory tree (default: flat scan only). "
        "Ignored when --files is set.",
    )
    # --- Summarization flags ---
    parser.add_argument(
        "--summarize",
        action="store_true",
        default=False,
        help="Re-summarize digest text via LLM before embedding (default: off — "
        "digests are already summaries, double-summarization is usually harmful).",
    )
    parser.add_argument(
        "--summary-model",
        default="deepseek-chat",
        help="LLM model for summarization (default: deepseek-chat)",
    )
    parser.add_argument(
        "--max-summary-chars",
        type=int,
        default=1024,
        help="Target summary length in characters (default: 1024)",
    )
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace):
    """Resolve lucy_data_root and storage paths, preferring CLI overrides."""
    cfg = ConfigManager("config.json")

    # --- lucy_data_root (where digests live) ---
    lucy_data_root = args.lucy_data_root
    if not lucy_data_root:
        lucy_data_root = cfg.get("external_roots", {}).get("lucy_data_files", "")
    if not lucy_data_root or "/tmp/pytest" in lucy_data_root:
        lucy_data_root = PROD_LUCY_DATA_ROOT

    # --- storage paths (where embeddings are persisted) ---
    storage_root = args.storage_root
    if not storage_root:
        storage_root = cfg.get("storage_root_path") or ""
    if not storage_root or "/tmp/pytest" in storage_root:
        storage_root = PROD_STORAGE_ROOT

    storage_ns = cfg.get("storage_namespace") or PROD_STORAGE_NS

    return lucy_data_root, storage_root, storage_ns


def already_embedded(storage: JsonFileStorage, account: str, record_id: str) -> bool:
    """Check if an embedding record already exists for this digest."""
    emb_dir = storage.storage_paths.base / "embeddings" / account / "digests"
    return (emb_dir / f"{record_id}.json").exists()


def summarize_text(
    text: str,
    *,
    llm_api: RouterApi,
    model: str = "deepseek-chat",
    max_chars: int = 1024,
) -> str:
    """Summarize digest text via LLM.

    Returns the summary, or the original text (truncated) on failure.
    """
    user_prompt = (
        f"Summarize this chat session digest to approximately {max_chars} characters. "
        "Preserve the key topics, decisions made, files modified, commands run, "
        "and open questions.\n\n---\n{text}"
    )

    messages = [
        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = llm_api.create_response(
            model=model,
            input=messages,
            temperature=0.0,
        )
        summary = response.output_text.strip()
        if summary:
            return summary
    except Exception:
        logging.exception("summarize_text: LLM call failed — falling back to raw text")

    # Fallback: truncate raw text
    return text[:max_chars * 4]  # generous fallback


def _collect_files(
    args: argparse.Namespace, digests_dir: Path
) -> list[Path]:
    """Collect digest files based on --files, --recursive, or default flat scan.

    Returns sorted list of Path objects.
    """
    # --files takes priority
    if args.files:
        paths: list[Path] = []
        for raw in args.files.split(","):
            raw = raw.strip()
            if not raw:
                continue
            p = Path(raw)
            if not p.is_absolute():
                p = digests_dir / p
            if not p.exists():
                print(f"  WARNING: file not found — skipping: {p}")
                continue
            if p.suffix != ".md":
                print(f"  WARNING: not a .md file — skipping: {p}")
                continue
            paths.append(p)
        if not paths:
            print("No valid .md files found from --files list.")
            sys.exit(0)
        return sorted(paths)

    # --recursive: scan all subdirectories
    if args.recursive:
        return sorted(digests_dir.rglob("*.md"))

    # Default: flat scan only
    return sorted(digests_dir.glob("*.md"))


def main() -> None:
    args = parse_args()
    lucy_data_root, storage_root, storage_ns = resolve_paths(args)

    # Build storage and embedding facade
    sp = StoragePaths(storage_root, storage_ns)
    storage = JsonFileStorage(sp)
    facade = EmbeddingFacade()

    # Build LLM router (only needed if summarization is on)
    llm_api: RouterApi | None = None
    if args.summarize:
        llm_api = RouterApi()

    # Locate digest files
    digests_dir = Path(lucy_data_root) / "data" / "digests" / args.account
    if not digests_dir.exists():
        print(f"Digests directory not found: {digests_dir}")
        sys.exit(1)

    digest_files = _collect_files(args, digests_dir)
    if not digest_files:
        print(f"No .md files found in {digests_dir}")
        sys.exit(0)

    print(f"Digests dir:  {digests_dir}")
    print(f"Embeddings:   {sp.base / 'embeddings' / args.account / 'digests'}")
    print(f"Found {len(digest_files)} digest files")
    if args.files:
        print(f"Mode:         --files (explicit list)")
    elif args.recursive:
        print(f"Mode:         --recursive (rglob)")
    else:
        print(f"Mode:         flat scan (default)")
    print(f"Embed model:  {args.model}")
    print(f"Summarize:    {'yes' if args.summarize else 'no'}  |  "
          f"Summary model: {args.summary_model if args.summarize else 'N/A'}  |  "
          f"Max summary: {args.max_summary_chars} chars")
    print(f"Min chars:    {args.min_chars}")
    if args.dry_run:
        print("*** DRY RUN — nothing will be embedded or persisted ***")
    if args.force:
        print("*** FORCE — will re-embed even existing records ***")
    print("-" * 60)

    skipped_empty = 0
    skipped_exists = 0
    embedded = 0
    errors = 0

    for md_file in digest_files:
        record_id = md_file.stem  # filename without .md

        # Check if already exists
        if not args.force and already_embedded(storage, args.account, record_id):
            print(f"  SKIP (exists): {md_file.name}")
            skipped_exists += 1
            continue

        # Read digest text
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ERROR reading {md_file.name}: {e}")
            errors += 1
            continue

        # Skip too-short digests
        if len(text.strip()) < args.min_chars:
            print(f"  SKIP (too short, {len(text.strip())} chars): {md_file.name}")
            skipped_empty += 1
            continue

        # --- Summarize (opt-in — off by default for digests) ---
        embed_text = text
        source_metadata: dict = {
            "path": str(md_file),
            "session_id": (
                record_id.split("_")[0] if "_" in record_id else record_id
            ),
            "full_text_chars": len(text),
        }

        if args.summarize and llm_api is not None:
            print(f"  SUMMARIZING: {md_file.name} ({len(text)} chars)", end=" ... ")
            embed_text = summarize_text(
                text,
                llm_api=llm_api,
                model=args.summary_model,
                max_chars=args.max_summary_chars,
            )
            source_metadata["summary_text"] = embed_text
            source_metadata["summary_model"] = args.summary_model
            print(f"→ {len(embed_text)} chars")

        if args.dry_run:
            print(f"  WOULD embed: {md_file.name} ({len(embed_text)} chars)")
            embedded += 1
            continue

        # Generate embedding
        try:
            resp = facade.embed([embed_text], model=args.model)
            vector = resp.embeddings[0]
        except Exception as e:
            print(f"  ERROR embedding {md_file.name}: {e}")
            errors += 1
            continue

        # Build and persist EmbeddingRecord
        try:
            record = EmbeddingRecord(
                id=record_id,
                namespace="digests",
                account_name=args.account,
                vector=vector,
                source_type="digest",
                source_id=(
                    record_id.split("_")[0] if "_" in record_id else record_id
                ),
                source_metadata=source_metadata,
            )
            storage.upsert_embedding(record)
            print(f"  EMBEDDED: {md_file.name} ({len(embed_text)} chars)")
            embedded += 1
        except Exception as e:
            print(f"  ERROR persisting {md_file.name}: {e}")
            errors += 1
            continue

    print("-" * 60)
    print(
        f"Summary: {embedded} embedded, {skipped_exists} skipped (exists), "
        f"{skipped_empty} skipped (empty/short), {errors} errors"
    )


if __name__ == "__main__":
    main()
