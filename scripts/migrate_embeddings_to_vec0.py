from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import StoreKey
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import PrimitivesEmbeddingStore
from src.storage.vec0_embedding_store import DEFAULT_SQLITE_VEC_EXTENSION_PATH

_EMBEDDING_DIM = 1536

_VEC_TABLE_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0("
    " id TEXT,"
    " embedding float[1536] distance_metric=cosine,"
    " account_name TEXT,"
    " namespace TEXT,"
    " source_type TEXT)"
)

_METADATA_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS embedding_metadata ("
    " id TEXT PRIMARY KEY,"
    " account_name TEXT NOT NULL,"
    " namespace TEXT NOT NULL,"
    " source_type TEXT NOT NULL DEFAULT '',"
    " source_id TEXT NOT NULL DEFAULT '',"
    " source_metadata TEXT NOT NULL DEFAULT '{}',"
    " created_at TEXT NOT NULL)"
)

_ACCOUNT_NS_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_emb_meta_account_ns"
    " ON embedding_metadata(account_name, namespace)"
)

_SOURCE_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_emb_meta_source"
    " ON embedding_metadata(source_type, source_id)"
)

_VEC_INSERT_SQL = (
    "INSERT INTO vec_embeddings(id, account_name, namespace, source_type, embedding)"
    " VALUES (?, ?, ?, ?, ?)"
)

_VEC_SELECT_ROWIDS_SQL = "SELECT rowid FROM vec_embeddings WHERE id = ?"

_VEC_DELETE_BY_ROWID_SQL = "DELETE FROM vec_embeddings WHERE rowid = ?"

_METADATA_UPSERT_SQL = (
    "INSERT INTO embedding_metadata("
    " id, account_name, namespace, source_type, source_id, source_metadata, created_at"
    ") VALUES (?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(id) DO UPDATE SET"
    " account_name = excluded.account_name,"
    " namespace = excluded.namespace,"
    " source_type = excluded.source_type,"
    " source_id = excluded.source_id,"
    " source_metadata = excluded.source_metadata,"
    " created_at = excluded.created_at"
)

_VEC_COUNTS_SQL = (
    "SELECT namespace, COUNT(*) FROM vec_embeddings"
    " WHERE account_name = ? GROUP BY namespace"
)

_METADATA_COUNTS_SQL = (
    "SELECT namespace, COUNT(*) FROM embedding_metadata"
    " WHERE account_name = ? GROUP BY namespace"
)


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _upsert_record(conn: sqlite3.Connection, record: EmbeddingRecord) -> None:
    rowids = conn.execute(_VEC_SELECT_ROWIDS_SQL, (record.id,)).fetchall()
    for (rowid,) in rowids:
        conn.execute(_VEC_DELETE_BY_ROWID_SQL, (rowid,))
    conn.execute(
        _VEC_INSERT_SQL,
        (
            record.id,
            record.account_name,
            record.namespace,
            record.source_type,
            json.dumps(record.vector),
        ),
    )
    conn.execute(
        _METADATA_UPSERT_SQL,
        (
            record.id,
            record.account_name,
            record.namespace,
            record.source_type,
            record.source_id,
            json.dumps(record.source_metadata or {}),
            _to_utc_iso(record.created_at),
        ),
    )


def migrate_embeddings_to_vec0(
    db_path: str,
    account: str,
    extension_path: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    log=print,
) -> Dict[str, Any]:
    prefix = f"embeddings/{account}/"
    if not Path(db_path).exists():
        raise FileNotFoundError(f"database does not exist: {db_path}")

    store = SqliteChat2Primitives(db_path)
    try:
        keys = store.list_keys(StoreKey(prefix))
        raw_docs: List[Tuple[StoreKey, str]] = []
        for key in keys:
            raw = store.read_text(key)
            if raw is not None:
                raw_docs.append((key, raw))
    finally:
        store.close()

    records: List[EmbeddingRecord] = []
    skipped: List[str] = []
    for key, raw in raw_docs:
        parts = key.value.split("/")
        if len(parts) < 4 or not parts[-1].endswith(".json"):
            skipped.append(key.value)
            continue
        record = PrimitivesEmbeddingStore._from_doc(StoreKey(key.value), raw)
        if (
            record is None
            or not record.id
            or not record.namespace
            or not record.account_name
        ):
            skipped.append(key.value)
            continue
        if len(record.vector) != _EMBEDDING_DIM:
            raise ValueError(
                f"record {record.id!r} in namespace {record.namespace!r} has"
                f" {len(record.vector)}-dim vector, expected {_EMBEDDING_DIM}"
                f" (key {key.value})"
            )
        if verbose:
            log(f"  {key.value}")
        records.append(record)

    parsed_counts: Dict[str, int] = {}
    for record in records:
        parsed_counts[record.namespace] = parsed_counts.get(record.namespace, 0) + 1

    summary: Dict[str, Any] = {
        "account": account,
        "db_path": db_path,
        "total_keys": len(keys),
        "parsed_counts": parsed_counts,
        "skipped": skipped,
        "dry_run": dry_run,
        "vec_counts": None,
        "metadata_counts": None,
    }

    if dry_run:
        return summary

    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.enable_load_extension(True)
        conn.load_extension(extension_path)
        conn.execute(_VEC_TABLE_DDL)
        conn.execute(_METADATA_TABLE_DDL)
        conn.execute(_ACCOUNT_NS_INDEX_DDL)
        conn.execute(_SOURCE_INDEX_DDL)
        conn.execute("BEGIN")
        try:
            for record in records:
                _upsert_record(conn, record)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        vec_counts = {
            row[0]: row[1]
            for row in conn.execute(_VEC_COUNTS_SQL, (account,)).fetchall()
        }
        metadata_counts = {
            row[0]: row[1]
            for row in conn.execute(_METADATA_COUNTS_SQL, (account,)).fetchall()
        }
    finally:
        conn.close()

    summary["vec_counts"] = vec_counts
    summary["metadata_counts"] = metadata_counts
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate kv embedding documents into sqlite-vec vec0 tables"
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
    parser.add_argument(
        "--account",
        default="junwin",
        help="Account whose embeddings/<account>/ kv keys are migrated (default: junwin)",
    )
    parser.add_argument(
        "--extension-path",
        default=DEFAULT_SQLITE_VEC_EXTENSION_PATH,
        help="Path to the loadable sqlite-vec extension (default: the /usr/local path)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and report only; write nothing"
    )
    parser.add_argument("--verbose", action="store_true", help="Log each key parsed")

    args = parser.parse_args(argv)

    db_path = args.db_path
    if not db_path:
        base = Path(args.base_path)
        ns = args.storage_namespace
        db_path = str(base / ns / "embeddings.sqlite")

    if not Path(db_path).exists():
        print(f"[ERROR] database does not exist: {db_path}")
        return 1

    if not args.dry_run and not Path(args.extension_path).exists():
        print(f"[ERROR] sqlite-vec extension not found: {args.extension_path}")
        return 1

    print(f"DB:       {db_path}")
    print(f"Account:  {args.account}")
    print(f"Extension: {args.extension_path}")

    try:
        summary = migrate_embeddings_to_vec0(
            db_path,
            args.account,
            args.extension_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    total_keys = summary["total_keys"]
    parsed_counts = summary["parsed_counts"]
    skipped = summary["skipped"]

    print(f"kv keys under embeddings/{args.account}/: {total_keys}")
    for ns in sorted(parsed_counts):
        print(f"  kv {ns}: {parsed_counts[ns]}")

    if skipped:
        print(f"[WARN] skipped {len(skipped)} key(s):")
        for key in skipped:
            print(f"  {key}")

    if summary["dry_run"]:
        total = sum(parsed_counts.values())
        print(
            f"[DRY-RUN] Would upsert {total} record(s) into vec_embeddings +"
            " embedding_metadata; kv documents left untouched."
        )
        return 0

    vec_counts = summary["vec_counts"] or {}
    metadata_counts = summary["metadata_counts"] or {}
    total_migrated = sum(parsed_counts.values())

    print("Per-namespace counts (parsed kv / vec_embeddings / embedding_metadata):")
    namespaces = sorted(set(parsed_counts) | set(vec_counts) | set(metadata_counts))
    for ns in namespaces:
        print(
            f"  {ns}: {parsed_counts.get(ns, 0)} / {vec_counts.get(ns, 0)}"
            f" / {metadata_counts.get(ns, 0)}"
        )
    print(
        f"Totals: {total_migrated} / {sum(vec_counts.values())}"
        f" / {sum(metadata_counts.values())}"
    )

    mismatches: List[str] = []
    for ns in namespaces:
        parsed_n = parsed_counts.get(ns, 0)
        vec_n = vec_counts.get(ns, 0)
        meta_n = metadata_counts.get(ns, 0)
        if not (parsed_n == vec_n == meta_n):
            mismatches.append(
                f"namespace {ns}: parsed={parsed_n} vec={vec_n} metadata={meta_n}"
            )

    if mismatches:
        print("[ERROR] verification failed:")
        for line in mismatches:
            print(f"  {line}")
        return 1

    print(
        f"[OK] migrated {total_migrated} record(s); per-namespace vec/metadata"
        " counts match the kv records."
    )
    print("kv documents were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
