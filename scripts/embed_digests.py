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

Reads .md digest files from <lucy_data_root>/data/digests/<account>/ and
persists them as EmbeddingRecords through the configured embedding backend
(``build_primitives_embedding_store`` honoring ``embedding_store_backend``;
default ``file`` keeps the legacy JsonFileStorage on-disk layout).

The pass is a namespace sync: files whose stored ``content_hash`` (sha256 of
the source bytes) matches are skipped, changed or un-hashed files are
re-embedded under the same record id (digest filename stem), and records
whose digest file vanished under the digests directory are pruned by record
id only — never by source_id (a session id is shared by every digest of that
session, so source_id-based deletes would over-delete; see #90/#81).

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
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_manager import ConfigManager
from src.embeddings.facade import EmbeddingFacade
from galet.router_api import RouterApi
from scripts.embed_sync import StoreConfig, is_unchanged, prune_missing, sha256_file
from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import build_primitives_embedding_store

logging.basicConfig(level=logging.WARNING)

PROD_LUCY_DATA_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_NS = "data"

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


def resolve_paths(
    args: argparse.Namespace, cfg: ConfigManager
) -> tuple[str, str, str]:
    lucy_data_root = args.lucy_data_root
    if not lucy_data_root:
        lucy_data_root = cfg.get("external_roots", {}).get("lucy_data_files", "")
    if not lucy_data_root or "/tmp/pytest" in lucy_data_root:
        lucy_data_root = PROD_LUCY_DATA_ROOT

    storage_root = args.storage_root
    if not storage_root:
        storage_root = cfg.get("storage_root_path") or ""
    if not storage_root or "/tmp/pytest" in storage_root:
        storage_root = PROD_STORAGE_ROOT

    storage_ns = cfg.get("storage_namespace") or PROD_STORAGE_NS

    return lucy_data_root, storage_root, storage_ns


def summarize_text(
    text: str,
    *,
    llm_api: RouterApi,
    model: str = "deepseek-chat",
    max_chars: int = 1024,
) -> str:
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

    return text[: max_chars * 4]


def _collect_files(args: argparse.Namespace, digests_dir: Path) -> list[Path]:
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

    if args.recursive:
        return sorted(digests_dir.rglob("*.md"))

    return sorted(digests_dir.glob("*.md"))


def sync_digests(
    *,
    store: EmbeddingStore,
    account: str,
    digests_dir: Path,
    digest_files: List[Path],
    embed_fn: Callable[[str], List[float]],
    summarize_fn: Optional[Callable[[str], str]] = None,
    summary_model: str = "deepseek-chat",
    min_chars: int = 100,
    force: bool = False,
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> Dict[str, int]:
    existing_by_id: Dict[str, EmbeddingRecord] = {}
    if not force:
        for record in store.list_embeddings("digests", account):
            existing_by_id[record.id] = record

    counts: Dict[str, int] = {
        "embedded": 0,
        "skipped": 0,
        "skipped_empty": 0,
        "pruned": 0,
        "errors": 0,
    }

    for md_file in digest_files:
        record_id = md_file.stem
        current_hash = sha256_file(md_file)

        if not force and is_unchanged(existing_by_id.get(record_id), current_hash):
            log(f"  SKIP (unchanged): {md_file.name}")
            counts["skipped"] += 1
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            log(f"  ERROR reading {md_file.name}: {e}")
            counts["errors"] += 1
            continue

        if len(text.strip()) < min_chars:
            log(f"  SKIP (too short, {len(text.strip())} chars): {md_file.name}")
            counts["skipped_empty"] += 1
            continue

        session_id = record_id.split("_")[0] if "_" in record_id else record_id
        embed_text = text
        source_metadata: Dict[str, Any] = {
            "path": str(md_file),
            "session_id": session_id,
            "full_text_chars": len(text),
            "content_hash": current_hash,
        }

        if summarize_fn is not None:
            embed_text = summarize_fn(text)
            source_metadata["summary_text"] = embed_text
            source_metadata["summary_model"] = summary_model
            log(
                f"  SUMMARIZING: {md_file.name} ({len(text)} chars) "
                f"→ {len(embed_text)} chars"
            )

        if dry_run:
            log(f"  WOULD embed: {md_file.name} ({len(embed_text)} chars)")
            counts["embedded"] += 1
            continue

        try:
            vector = embed_fn(embed_text)
        except Exception as e:
            log(f"  ERROR embedding {md_file.name}: {e}")
            counts["errors"] += 1
            continue

        try:
            record = EmbeddingRecord(
                id=record_id,
                namespace="digests",
                account_name=account,
                vector=vector,
                source_type="digest",
                source_id=session_id,
                source_metadata=source_metadata,
            )
            store.upsert_embedding(record)
            log(f"  EMBEDDED: {md_file.name} ({len(embed_text)} chars)")
            counts["embedded"] += 1
        except Exception as e:
            log(f"  ERROR persisting {md_file.name}: {e}")
            counts["errors"] += 1
            continue

    pruned_ids = prune_missing(
        store,
        account_name=account,
        namespace="digests",
        source_root=digests_dir,
        dry_run=dry_run,
        log=log,
    )
    counts["pruned"] = len(pruned_ids)
    return counts


def main() -> None:
    args = parse_args()
    cfg = ConfigManager("config.json")
    lucy_data_root, storage_root, storage_ns = resolve_paths(args, cfg)

    store = build_primitives_embedding_store(
        StoreConfig(cfg, storage_root=storage_root, storage_namespace=storage_ns)
    )
    facade = EmbeddingFacade()

    digests_dir = (
        Path(lucy_data_root) / "data" / "digests" / args.account
    ).resolve()
    if not digests_dir.exists():
        print(f"Digests directory not found: {digests_dir}")
        sys.exit(1)

    digest_files = _collect_files(args, digests_dir)
    if not digest_files:
        print(f"No .md files found in {digests_dir}")
        sys.exit(0)

    summarize_fn: Optional[Callable[[str], str]] = None
    if args.summarize:
        llm_api = RouterApi()

        def summarize_one(text: str) -> str:
            return summarize_text(
                text,
                llm_api=llm_api,
                model=args.summary_model,
                max_chars=args.max_summary_chars,
            )

        summarize_fn = summarize_one

    backend_name = str(cfg.get("embedding_store_backend") or "file")
    print(f"Digests dir:  {digests_dir}")
    print(f"Store:        {type(store).__name__} (backend: {backend_name})")
    print(f"Found {len(digest_files)} digest files")
    if args.files:
        print(f"Mode:         --files (explicit list)")
    elif args.recursive:
        print(f"Mode:         --recursive (rglob)")
    else:
        print(f"Mode:         flat scan (default)")
    print(f"Embed model:  {args.model}")
    print(
        f"Summarize:    {'yes' if args.summarize else 'no'}  |  "
        f"Summary model: {args.summary_model if args.summarize else 'N/A'}  |  "
        f"Max summary: {args.max_summary_chars} chars"
    )
    print(f"Min chars:    {args.min_chars}")
    if args.dry_run:
        print("*** DRY RUN — nothing will be embedded or persisted ***")
    if args.force:
        print("*** FORCE — will re-embed even existing records ***")
    print("-" * 60)

    def embed_one(text: str) -> List[float]:
        return facade.embed([text], model=args.model).embeddings[0]

    counts = sync_digests(
        store=store,
        account=args.account,
        digests_dir=digests_dir,
        digest_files=digest_files,
        embed_fn=embed_one,
        summarize_fn=summarize_fn,
        summary_model=args.summary_model,
        min_chars=args.min_chars,
        force=args.force,
        dry_run=args.dry_run,
    )

    print("-" * 60)
    print(
        f"Summary: {counts['embedded']} embedded, "
        f"{counts['skipped']} skipped (unchanged), "
        f"{counts['skipped_empty']} skipped (empty/short), "
        f"{counts['pruned']} pruned, {counts['errors']} errors"
    )


if __name__ == "__main__":
    main()
