#!/usr/bin/env python3
"""Batch-embed markdown files from an external folder into the embedding store.

Usage:
    python scripts/embed_external.py /path/to/docs --namespace books
    python scripts/embed_external.py /path/to/docs --namespace books --dry-run
    python scripts/embed_external.py /path/to/docs --namespace external --source-type obsidian_note
    python scripts/embed_external.py /path/to/docs --namespace books --recursive
    python scripts/embed_external.py /path/to/docs --namespace books --no-summarize

Walks a folder (optionally recursively), reads .md files, summarizes them via
LLM (default: on), generates embeddings via EmbeddingFacade, and persists
them through the configured embedding backend
(``build_primitives_embedding_store`` honoring ``embedding_store_backend``;
default ``file`` keeps the legacy JsonFileStorage on-disk layout).

The pass is a namespace sync: files whose stored ``content_hash`` (sha256 of
the source bytes) matches are skipped, changed or un-hashed files are
re-embedded under the same record id, and records whose source file vanished
under the managed source folder are pruned by record id (never by source_id).

Summarization is on by default because external documents (books, notes, etc.)
are full-length — not summaries. Pass --no-summarize to embed raw text.

If config.json has test paths (e.g. /tmp/pytest-*), use --storage-root to override.
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

PROD_STORAGE_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_NS = "data"

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a concise summarizer. Your job is to distill a document into a "
    "short, searchable summary. Preserve: key topics, people, terminology, "
    "decisions, and conclusions. Drop boilerplate, table-of-contents, "
    "formatting-only lines, and repetitive filler. Output plain text — "
    "no Markdown formatting."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-embed external markdown files")
    parser.add_argument(
        "source_dir",
        help="Path to the folder containing .md files to embed",
    )
    parser.add_argument(
        "--namespace",
        required=True,
        help="Embedding namespace (e.g. 'books', 'external', 'obsidian')",
    )
    parser.add_argument(
        "--source-type",
        default=None,
        help="source_type for EmbeddingRecord (default: same as --namespace)",
    )
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
        "--recursive",
        action="store_true",
        help="Walk subdirectories (default: top-level only)",
    )
    parser.add_argument(
        "--storage-root",
        default=None,
        help="Override storage_root_path (embeddings persisted under <root>/data/embeddings/)",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        default=True,
        help="Summarize document text via LLM before embedding (default: on — "
        "full documents need summary-concentration for good embedding search).",
    )
    parser.add_argument(
        "--no-summarize",
        action="store_false",
        dest="summarize",
        help="Embed raw document text — skip LLM summarization.",
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


def resolve_storage_paths(
    args: argparse.Namespace, cfg: ConfigManager
) -> tuple[str, str]:
    storage_root = args.storage_root
    if not storage_root:
        storage_root = cfg.get("storage_root_path") or ""
    if not storage_root or "/tmp/pytest" in storage_root:
        storage_root = PROD_STORAGE_ROOT

    storage_ns = cfg.get("storage_namespace") or PROD_STORAGE_NS
    return storage_root, storage_ns


def record_id_from_file(source_root: Path, md_file: Path) -> str:
    rel = md_file.relative_to(source_root)
    return str(rel.with_suffix("")).replace("/", "_").replace("\\", "_")


def summarize_text(
    text: str,
    *,
    llm_api: RouterApi,
    model: str = "deepseek-chat",
    max_chars: int = 1024,
) -> str:
    user_prompt = (
        f"Summarize this document to approximately {max_chars} characters. "
        "Preserve the key topics, people, terminology, decisions, and conclusions.\n\n"
        f"---\n{text}"
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


def sync_directory(
    *,
    store: EmbeddingStore,
    account: str,
    namespace: str,
    source_type: str,
    source_dir: Path,
    md_files: List[Path],
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
        for record in store.list_embeddings(namespace, account):
            existing_by_id[record.id] = record

    counts: Dict[str, int] = {
        "embedded": 0,
        "skipped": 0,
        "skipped_empty": 0,
        "pruned": 0,
        "errors": 0,
    }

    for md_file in md_files:
        record_id = record_id_from_file(source_dir, md_file)
        relative = md_file.relative_to(source_dir)
        current_hash = sha256_file(md_file)

        if not force and is_unchanged(existing_by_id.get(record_id), current_hash):
            log(f"  SKIP (unchanged): {relative}")
            counts["skipped"] += 1
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            log(f"  ERROR reading {relative}: {e}")
            counts["errors"] += 1
            continue

        if len(text.strip()) < min_chars:
            log(f"  SKIP (too short, {len(text.strip())} chars): {relative}")
            counts["skipped_empty"] += 1
            continue

        embed_text = text
        source_metadata: Dict[str, Any] = {
            "path": str(md_file),
            "relative_path": str(relative),
            "full_text_chars": len(text),
            "content_hash": current_hash,
        }

        if summarize_fn is not None:
            embed_text = summarize_fn(text)
            source_metadata["summary_text"] = embed_text
            source_metadata["summary_model"] = summary_model
            log(
                f"  SUMMARIZING: {relative} ({len(text)} chars) "
                f"→ {len(embed_text)} chars"
            )

        if dry_run:
            log(f"  WOULD embed: {relative} ({len(embed_text)} chars)")
            counts["embedded"] += 1
            continue

        try:
            vector = embed_fn(embed_text)
        except Exception as e:
            log(f"  ERROR embedding {relative}: {e}")
            counts["errors"] += 1
            continue

        try:
            record = EmbeddingRecord(
                id=record_id,
                namespace=namespace,
                account_name=account,
                vector=vector,
                source_type=source_type,
                source_id=str(relative),
                source_metadata=source_metadata,
            )
            store.upsert_embedding(record)
            log(f"  EMBEDDED: {relative} ({len(embed_text)} chars)")
            counts["embedded"] += 1
        except Exception as e:
            log(f"  ERROR persisting {relative}: {e}")
            counts["errors"] += 1
            continue

    pruned_ids = prune_missing(
        store,
        account_name=account,
        namespace=namespace,
        source_root=source_dir,
        dry_run=dry_run,
        log=log,
    )
    counts["pruned"] = len(pruned_ids)
    return counts


def main() -> None:
    args = parse_args()
    source_type = args.source_type or args.namespace
    cfg = ConfigManager("config.json")
    storage_root, storage_ns = resolve_storage_paths(args, cfg)

    source_dir = Path(args.source_dir).expanduser().resolve()
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        sys.exit(1)
    if not source_dir.is_dir():
        print(f"Not a directory: {source_dir}")
        sys.exit(1)

    store = build_primitives_embedding_store(
        StoreConfig(cfg, storage_root=storage_root, storage_namespace=storage_ns)
    )
    facade = EmbeddingFacade()

    if args.recursive:
        md_files = sorted(source_dir.rglob("*.md"))
    else:
        md_files = sorted(source_dir.glob("*.md"))

    if not md_files:
        print(f"No .md files found in {source_dir}")
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
    print(f"Source dir:   {source_dir}")
    print(f"Store:        {type(store).__name__} (backend: {backend_name})")
    print(f"Namespace:    {args.namespace}")
    print(f"Source type:  {source_type}")
    print(f"Found {len(md_files)} .md files")
    print(f"Embed model:  {args.model}  |  Min chars: {args.min_chars}")
    print(
        f"Summarize:    {'yes' if args.summarize else 'no'}  |  "
        f"Summary model: {args.summary_model if args.summarize else 'N/A'}  |  "
        f"Max summary: {args.max_summary_chars} chars"
    )
    if args.dry_run:
        print("*** DRY RUN — nothing will be embedded or persisted ***")
    if args.force:
        print("*** FORCE — will re-embed even unchanged records ***")
    if args.recursive:
        print("*** RECURSIVE — walking subdirectories ***")
    print("-" * 60)

    def embed_one(text: str) -> List[float]:
        return facade.embed([text], model=args.model).embeddings[0]

    counts = sync_directory(
        store=store,
        account=args.account,
        namespace=args.namespace,
        source_type=source_type,
        source_dir=source_dir,
        md_files=md_files,
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
