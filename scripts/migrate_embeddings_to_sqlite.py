#!/usr/bin/env python3
"""
migrate_embeddings_to_sqlite.py

Copy embedding records from the file-based embedding store to the SQLite
embedding store, using the generic-store primitives protocol on both sides.

One-time lift, not a sync: this script copies whatever records currently
exist in the file store into SQLite as-is. It never prunes records whose
source file vanished and never refreshes changed content - no content
hashes are compared or written. Re-running it cannot repair a stale or
drifted target; the namespace sync (embed scripts) owns refresh and prune.

The two stores speak the same Chat2Primitives document protocol
(read_text / write_text / exists / delete / list_keys), so a migration is a
straight key-by-key copy under the "embeddings/" prefix:

    FileChat2Primitives(root)  --list_keys/read_text-->  SqliteChat2Primitives(db)

Keys are preserved verbatim (``embeddings/<account>/<namespace>/<id>.json``),
so the SQLite database ends up with exactly the same logical layout as the
files. Values are copied byte-for-byte (no re-serialization), which keeps
records lossless regardless of their JSON shape.

Behavior:
- Idempotent: re-running overwrites the same keys (write_text upserts).
- Non-destructive by default: source files are left in place. Pass
  --prune-files to delete a source file only after its copy succeeded
  (source-store lift cleanup - not a sync prune of target records).
- --dry-run shows what would be copied without writing to SQLite.
- --self-test runs a small built-in check in a temp dir and exits.

Usage examples:
  python scripts/migrate_embeddings_to_sqlite.py --dry-run
  python scripts/migrate_embeddings_to_sqlite.py --verbose
  python scripts/migrate_embeddings_to_sqlite.py --base-path /home/junwin/lucy_storage --storage-namespace data
  python scripts/migrate_embeddings_to_sqlite.py --db-path /tmp/embeddings.sqlite
  python scripts/migrate_embeddings_to_sqlite.py --prune-files
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import StoreKey

EMBEDDINGS_PREFIX = "embeddings/"


def migrate_embeddings(
    file_store: FileChat2Primitives,
    sqlite_store: SqliteChat2Primitives,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    log=print,
) -> tuple[int, int, list[str]]:
    """Copy embedding docs from ``file_store`` to ``sqlite_store``.

    Returns ``(total, copied, skipped)`` where ``skipped`` lists the key
    values that were not copied (malformed layout or unreadable file).
    """
    keys = sorted(file_store.list_keys(StoreKey(EMBEDDINGS_PREFIX)), key=lambda k: k.value)
    total = len(keys)
    copied = 0
    skipped: list[str] = []

    for key in keys:
        parts = key.value.split("/")
        # Expect: embeddings/<account>/<namespace>/<id>.json
        if len(parts) < 4 or not parts[-1].endswith(".json"):
            skipped.append(key.value)
            continue

        raw = file_store.read_text(key)
        if raw is None:
            skipped.append(key.value)
            continue

        if verbose:
            log(f"  {key.value}")
        if not dry_run:
            sqlite_store.write_text(key, raw)
        copied += 1

    return total, copied, skipped


def _self_test() -> bool:
    """Run a small built-in check in a temp dir; returns True on success."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Fake file layout: two accounts/namespaces, plus a stray top-level file.
        emb = root / "embeddings"
        (emb / "junwin" / "vol_5").mkdir(parents=True)
        (emb / "alice" / "books").mkdir(parents=True)
        record = '{"id": "r1", "namespace": "vol_5", "account_name": "junwin", "vector": [0.1, 0.2]}'
        (emb / "junwin" / "vol_5" / "r1.json").write_text(record, encoding="utf-8")
        (emb / "alice" / "books" / "b1.json").write_text(
            '{"id": "b1", "namespace": "books", "account_name": "alice", "vector": [0.3]}',
            encoding="utf-8",
        )
        (emb / "stray.json").write_text("{}", encoding="utf-8")  # malformed layout

        file_store = FileChat2Primitives(root)
        sqlite_store = SqliteChat2Primitives(str(root / "embeddings.sqlite"))

        try:
            total, copied, skipped = migrate_embeddings(
                file_store, sqlite_store, verbose=False
            )
            if total != 3 or copied != 2:
                print(f"[SELF-TEST] expected total=3 copied=2, got total={total} copied={copied}")
                return False
            if skipped != ["embeddings/stray.json"]:
                print(f"[SELF-TEST] expected stray skip, got {skipped}")
                return False

            sqlite_keys = sqlite_store.list_keys(StoreKey(EMBEDDINGS_PREFIX))
            if len(sqlite_keys) != 2:
                print(f"[SELF-TEST] expected 2 keys in sqlite, got {len(sqlite_keys)}")
                return False

            # Byte-for-byte value check.
            for key in sqlite_keys:
                if sqlite_store.read_text(key) != file_store.read_text(key):
                    print(f"[SELF-TEST] value mismatch for {key.value}")
                    return False

            # Idempotency: re-run must not change the count.
            migrate_embeddings(file_store, sqlite_store)
            if len(sqlite_store.list_keys(StoreKey(EMBEDDINGS_PREFIX))) != 2:
                print("[SELF-TEST] re-run changed key count (not idempotent)")
                return False
        finally:
            sqlite_store.close()

        print("[SELF-TEST] Passed")
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-time lift of file-based embeddings into the SQLite embedding"
            " store (not a sync: never prunes target records, never refreshes"
            " changed content)"
        )
    )
    parser.add_argument(
        "--base-path",
        default=os.environ.get("LUCY_STORAGE_ROOT", "data"),
        help="Storage base path (default: LUCY_STORAGE_ROOT or 'data')",
    )
    parser.add_argument(
        "--storage-namespace",
        default=os.environ.get("LUCY_STORAGE_NAMESPACE", "data"),
        help="Storage namespace under base-path (default: LUCY_STORAGE_NAMESPACE or 'data')",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite db path (default: <base-path>/<namespace>/embeddings.sqlite)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write; just show what would be done")
    parser.add_argument(
        "--prune-files",
        action="store_true",
        help=(
            "Delete source files only after a successful copy"
            " (source-store lift cleanup - not a sync prune of target records)"
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Log each key copied")
    parser.add_argument("--self-test", action="store_true", help="Run a built-in self-check and exit")

    args = parser.parse_args(argv)

    if args.self_test:
        return 0 if _self_test() else 2

    base = Path(args.base_path)
    ns = args.storage_namespace
    file_root = base / ns
    db_path = Path(args.db_path) if args.db_path else file_root / "embeddings.sqlite"

    if not file_root.exists():
        print(f"[ERROR] file store root does not exist: {file_root}")
        return 1

    print(f"Source:  FileChat2Primitives({file_root})")
    print(f"Target:  SqliteChat2Primitives({db_path})")

    file_store = FileChat2Primitives(file_root)
    sqlite_store = SqliteChat2Primitives(str(db_path))
    try:
        total, copied, skipped = migrate_embeddings(
            file_store, sqlite_store, dry_run=args.dry_run, verbose=args.verbose
        )

        if skipped:
            print(f"[WARN] skipped {len(skipped)} key(s):")
            for k in skipped:
                print(f"  {k}")

        if args.dry_run:
            print(f"[DRY-RUN] Would copy {copied}/{total} embedding record(s).")
            return 0

        # Verify: count in sqlite matches copied.
        sqlite_count = len(sqlite_store.list_keys(StoreKey(EMBEDDINGS_PREFIX)))
        print(f"Copied {copied}/{total} record(s); sqlite now holds {sqlite_count} embedding key(s).")
        if sqlite_count != copied:
            print(f"[ERROR] verification failed: copied={copied} but sqlite holds {sqlite_count}")
            return 1

        if args.prune_files:
            pruned = 0
            for key in sqlite_store.list_keys(StoreKey(EMBEDDINGS_PREFIX)):
                # Only delete files that were actually copied.
                raw_sqlite = sqlite_store.read_text(key)
                raw_file = file_store.read_text(key)
                if raw_sqlite is not None and raw_file == raw_sqlite:
                    file_store.delete(key)
                    pruned += 1
            print(f"Pruned {pruned} source file(s).")
    finally:
        sqlite_store.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
