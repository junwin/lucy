#!/usr/bin/env python3
"""Batch-embed markdown files from an external folder into the embedding store.

Usage:
    python scripts/embed_external.py /path/to/docs --namespace books
    python scripts/embed_external.py /path/to/docs --namespace books --dry-run
    python scripts/embed_external.py /path/to/docs --namespace external --source-type obsidian_note
    python scripts/embed_external.py /path/to/docs --namespace books --recursive
    python scripts/embed_external.py /path/to/docs --namespace books --no-summarize

Walks a folder (optionally recursively), reads .md files, summarizes them via
LLM (default: on), generates embeddings via EmbeddingFacade, and persists them
via JsonFileStorage under:
    <storage_root>/data/embeddings/<account>/<namespace>/

Summarization is on by default because external documents (books, notes, etc.)
are full-length — not summaries. Summarization concentrates the signal for
embedding search. Pass --no-summarize to embed raw text instead.

Skips files that already have a matching embedding record (idempotent).

If config.json has test paths (e.g. /tmp/pytest-*), use --storage-root to override.
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
PROD_STORAGE_ROOT = "/home/junwin/lucy_storage"
PROD_STORAGE_NS = "data"

# ---------------------------------------------------------------------------
# Summarization prompt
# ---------------------------------------------------------------------------

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
    # --- Summarization flags ---
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


def resolve_storage_paths(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve storage paths, preferring CLI overrides over config."""
    cfg = ConfigManager("config.json")

    storage_root = args.storage_root
    if not storage_root:
        storage_root = cfg.get("storage_root_path") or ""
    if not storage_root or "/tmp/pytest" in storage_root:
        storage_root = PROD_STORAGE_ROOT

    storage_ns = cfg.get("storage_namespace") or PROD_STORAGE_NS
    return storage_root, storage_ns


def already_embedded(
    storage: JsonFileStorage, account: str, namespace: str, record_id: str
) -> bool:
    """Check if an embedding record already exists."""
    emb_dir = storage.storage_paths.base / "embeddings" / account / namespace
    return (emb_dir / f"{record_id}.json").exists()


def record_id_from_file(source_root: Path, md_file: Path) -> str:
    """Derive a unique record ID from the file path relative to source_root.

    Uses the relative path with path separators replaced by underscores.
    Example: subdir/notes.md -> subdir_notes
    """
    rel = md_file.relative_to(source_root)
    return str(rel.with_suffix("")).replace("/", "_").replace("\\", "_")


def summarize_text(
    text: str,
    *,
    llm_api: RouterApi,
    model: str = "deepseek-chat",
    max_chars: int = 1024,
) -> str:
    """Summarize document text via LLM.

    Returns the summary, or the original text (truncated) on failure.
    """
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

    # Fallback: truncate raw text
    return text[:max_chars * 4]  # generous fallback


def main() -> None:
    args = parse_args()
    source_type = args.source_type or args.namespace
    storage_root, storage_ns = resolve_storage_paths(args)

    source_dir = Path(args.source_dir).expanduser().resolve()
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        sys.exit(1)
    if not source_dir.is_dir():
        print(f"Not a directory: {source_dir}")
        sys.exit(1)

    # Build storage and embedding facade
    sp = StoragePaths(storage_root, storage_ns)
    storage = JsonFileStorage(sp)
    facade = EmbeddingFacade()

    # Build LLM router (needed when summarization is on — the default)
    llm_api: RouterApi | None = None
    if args.summarize:
        llm_api = RouterApi()

    # Locate markdown files
    if args.recursive:
        md_files = sorted(source_dir.rglob("*.md"))
    else:
        md_files = sorted(source_dir.glob("*.md"))

    if not md_files:
        print(f"No .md files found in {source_dir}")
        sys.exit(0)

    emb_dir = sp.base / "embeddings" / args.account / args.namespace

    print(f"Source dir:   {source_dir}")
    print(f"Embeddings:   {emb_dir}")
    print(f"Namespace:    {args.namespace}")
    print(f"Source type:  {source_type}")
    print(f"Found {len(md_files)} .md files")
    print(f"Embed model:  {args.model}  |  Min chars: {args.min_chars}")
    print(f"Summarize:    {'yes' if args.summarize else 'no'}  |  "
          f"Summary model: {args.summary_model if args.summarize else 'N/A'}  |  "
          f"Max summary: {args.max_summary_chars} chars")
    if args.dry_run:
        print("*** DRY RUN — nothing will be embedded or persisted ***")
    if args.force:
        print("*** FORCE — will re-embed even existing records ***")
    if args.recursive:
        print("*** RECURSIVE — walking subdirectories ***")
    print("-" * 60)

    skipped_empty = 0
    skipped_exists = 0
    embedded = 0
    errors = 0

    for md_file in md_files:
        record_id = record_id_from_file(source_dir, md_file)

        # Check if already exists
        if not args.force and already_embedded(
            storage, args.account, args.namespace, record_id
        ):
            print(f"  SKIP (exists): {md_file.relative_to(source_dir)}")
            skipped_exists += 1
            continue

        # Read file
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ERROR reading {md_file.relative_to(source_dir)}: {e}")
            errors += 1
            continue

        # Skip too-short files
        if len(text.strip()) < args.min_chars:
            print(
                f"  SKIP (too short, {len(text.strip())} chars): "
                f"{md_file.relative_to(source_dir)}"
            )
            skipped_empty += 1
            continue

        # --- Summarize (on by default for external docs) ---
        embed_text = text
        source_metadata: dict = {
            "path": str(md_file),
            "relative_path": str(md_file.relative_to(source_dir)),
            "full_text_chars": len(text),
        }

        if args.summarize and llm_api is not None:
            print(
                f"  SUMMARIZING: {md_file.relative_to(source_dir)} "
                f"({len(text)} chars)",
                end=" ... ",
            )
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
            print(
                f"  WOULD embed: {md_file.relative_to(source_dir)} "
                f"({len(embed_text)} chars)"
            )
            embedded += 1
            continue

        # Generate embedding
        try:
            resp = facade.embed([embed_text], model=args.model)
            vector = resp.embeddings[0]
        except Exception as e:
            print(f"  ERROR embedding {md_file.relative_to(source_dir)}: {e}")
            errors += 1
            continue

        # Build and persist EmbeddingRecord
        try:
            record = EmbeddingRecord(
                id=record_id,
                namespace=args.namespace,
                account_name=args.account,
                vector=vector,
                source_type=source_type,
                source_id=str(md_file.relative_to(source_dir)),
                source_metadata=source_metadata,
            )
            storage.upsert_embedding(record)
            print(
                f"  EMBEDDED: {md_file.relative_to(source_dir)} "
                f"({len(embed_text)} chars)"
            )
            embedded += 1
        except Exception as e:
            print(f"  ERROR persisting {md_file.relative_to(source_dir)}: {e}")
            errors += 1
            continue

    print("-" * 60)
    print(
        f"Summary: {embedded} embedded, {skipped_exists} skipped (exists), "
        f"{skipped_empty} skipped (empty/short), {errors} errors"
    )


if __name__ == "__main__":
    main()
