#!/usr/bin/env python3
"""Create vec_embeddings_v2 as a partition-key-free copy of vec_embeddings.

The destination table is created in the embeddings SQLite database with the
same columns, embedding dimensions, and distance metric as vec_embeddings,
minus the vec0 partition keys. Every row is copied with its ID and embedding
value preserved, and the destination is validated before the transaction
commits.

The script refuses to run when vec_embeddings_v2 already exists, stops at the
first error, and rolls the whole migration back on failure. The source table is
never modified.

Usage:
    python scripts/migrate_vec_embeddings_v2.py
    python scripts/migrate_vec_embeddings_v2.py --db-path /path/to/embeddings-v2.sqlite

Exit codes:
    0  vec_embeddings_v2 created and validated
    1  migration or validation failed (no partial destination left behind)
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage.vec0_embedding_store import DEFAULT_SQLITE_VEC_EXTENSION_PATH

SOURCE_TABLE = "vec_embeddings"
DESTINATION_TABLE = "vec_embeddings_v2"
DEFAULT_DB_PATH = Path("/home/junwin/lucy_storage/data/embeddings-v2.sqlite")

_FLOAT_DIMENSION_RE = re.compile(r"float\s*\[\s*(\d+)\s*\]", re.IGNORECASE)
_DISTANCE_METRIC_RE = re.compile(r"distance_metric\s*=\s*([A-Za-z_]+)", re.IGNORECASE)
_PARTITION_KEY_RE = re.compile(r"\s+partition\s+key", re.IGNORECASE)
_VIRTUAL_TABLE_PREFIX_RE = re.compile(
    r"^(CREATE\s+VIRTUAL\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(\"?[A-Za-z_][A-Za-z0-9_]*\"?)",
    re.IGNORECASE,
)


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _connect(db_path: Path, extension_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.enable_load_extension(True)
    conn.load_extension(extension_path)
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _table_ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    if row is None or not row[0]:
        raise ValueError(f"table not found in database: {table}")
    return str(row[0])


def _column_names(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({_quoted(table)})").fetchall()
    if not rows:
        raise ValueError(f"table declares no columns: {table}")
    return [str(row[1]) for row in rows]


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    if row is None:
        raise ValueError(f"validation query returned no result: {sql}")
    return int(row[0])


def _require_vec0_source(source_ddl: str) -> None:
    if "using vec0" not in source_ddl.lower():
        raise ValueError(f"{SOURCE_TABLE} is not a vec0 virtual table: {source_ddl!r}")


def _vector_signature(ddl: str) -> Tuple[int, str]:
    dimension = _FLOAT_DIMENSION_RE.search(ddl)
    if dimension is None:
        raise ValueError(f"vec0 schema declares no float dimension: {ddl!r}")
    metric = _DISTANCE_METRIC_RE.search(ddl)
    if metric is None:
        raise ValueError(f"vec0 schema declares no distance metric: {ddl!r}")
    return int(dimension.group(1)), metric.group(1).lower()


def destination_ddl(source_ddl: str) -> str:
    match = _VIRTUAL_TABLE_PREFIX_RE.match(source_ddl)
    if match is None:
        raise ValueError(f"cannot parse virtual table declaration: {source_ddl!r}")
    declared_name = match.group(2).strip('"')
    if declared_name.lower() != SOURCE_TABLE.lower():
        raise ValueError(
            f"unexpected virtual table name {declared_name!r} in {source_ddl!r}"
        )
    without_partition_keys = _PARTITION_KEY_RE.sub("", source_ddl)
    return match.group(1) + DESTINATION_TABLE + without_partition_keys[match.end() :]


def validate_schema(
    conn: sqlite3.Connection, source_ddl: str, expected_ddl: str
) -> Tuple[int, str]:
    actual_ddl = _table_ddl(conn, DESTINATION_TABLE)
    if actual_ddl != expected_ddl:
        raise ValueError(
            f"{DESTINATION_TABLE} schema mismatch: expected {expected_ddl!r}, "
            f"got {actual_ddl!r}"
        )
    if _PARTITION_KEY_RE.search(actual_ddl):
        raise ValueError(
            f"{DESTINATION_TABLE} still declares a partition key: {actual_ddl!r}"
        )

    source_signature = _vector_signature(source_ddl)
    destination_signature = _vector_signature(actual_ddl)
    if destination_signature != source_signature:
        raise ValueError(
            f"vector signature mismatch: {SOURCE_TABLE} {source_signature}, "
            f"{DESTINATION_TABLE} {destination_signature}"
        )

    source_columns = _column_names(conn, SOURCE_TABLE)
    destination_columns = _column_names(conn, DESTINATION_TABLE)
    if destination_columns != source_columns:
        raise ValueError(
            f"column mismatch: {SOURCE_TABLE} {source_columns}, "
            f"{DESTINATION_TABLE} {destination_columns}"
        )
    return destination_signature


def validate_rows(
    conn: sqlite3.Connection, columns: Sequence[str], dimension: int
) -> int:
    source_count = _scalar(conn, f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
    destination_count = _scalar(conn, f"SELECT COUNT(*) FROM {DESTINATION_TABLE}")
    if destination_count != source_count:
        raise ValueError(
            f"row count mismatch: {SOURCE_TABLE} has {source_count}, "
            f"{DESTINATION_TABLE} has {destination_count}"
        )

    missing = _scalar(
        conn,
        f"SELECT COUNT(*) FROM {SOURCE_TABLE} s LEFT JOIN {DESTINATION_TABLE} d"
        " ON d.id = s.id WHERE d.id IS NULL",
    )
    if missing:
        raise ValueError(
            f"{missing} {SOURCE_TABLE} id(s) are missing from {DESTINATION_TABLE}"
        )

    extra = _scalar(
        conn,
        f"SELECT COUNT(*) FROM {DESTINATION_TABLE} d LEFT JOIN {SOURCE_TABLE} s"
        " ON s.id = d.id WHERE s.id IS NULL",
    )
    if extra:
        raise ValueError(
            f"{extra} {DESTINATION_TABLE} id(s) are not present in {SOURCE_TABLE}"
        )

    equal_columns = " AND ".join(
        f"s.{_quoted(column)} IS d.{_quoted(column)}" for column in columns
    )
    differing = _scalar(
        conn,
        f"SELECT COUNT(*) FROM {SOURCE_TABLE} s JOIN {DESTINATION_TABLE} d"
        f" ON d.id = s.id WHERE NOT ({equal_columns})",
    )
    if differing:
        raise ValueError(
            f"{differing} row(s) differ between {SOURCE_TABLE} and {DESTINATION_TABLE}"
        )

    expected_bytes = dimension * 4
    wrong_size = _scalar(
        conn,
        f"SELECT COUNT(*) FROM {DESTINATION_TABLE}"
        f" WHERE length({_quoted('embedding')}) <> {expected_bytes}",
    )
    if wrong_size:
        raise ValueError(
            f"{wrong_size} {DESTINATION_TABLE} embedding value(s) are not "
            f"{expected_bytes} bytes ({dimension} float32 dimensions)"
        )
    return destination_count


def migrate_vec_embeddings_v2(db_path: Path, extension_path: str) -> Dict[str, Any]:
    resolved_db_path = db_path.expanduser().resolve()
    if not resolved_db_path.is_file():
        raise FileNotFoundError(f"embeddings database does not exist: {resolved_db_path}")
    if not Path(extension_path).is_file():
        raise FileNotFoundError(f"sqlite-vec extension not found: {extension_path}")

    conn = _connect(resolved_db_path, extension_path)
    try:
        if _table_exists(conn, DESTINATION_TABLE):
            raise FileExistsError(
                f"{DESTINATION_TABLE} already exists; refusing to overwrite: "
                f"{resolved_db_path}"
            )

        source_ddl = _table_ddl(conn, SOURCE_TABLE)
        _require_vec0_source(source_ddl)
        destination_schema = destination_ddl(source_ddl)
        columns = _column_names(conn, SOURCE_TABLE)
        column_list = ", ".join(_quoted(column) for column in columns)

        conn.execute("BEGIN")
        try:
            conn.execute(destination_schema)
            conn.execute(
                f"INSERT INTO {DESTINATION_TABLE} ({column_list})"
                f" SELECT {column_list} FROM {SOURCE_TABLE}"
            )
            dimension, distance_metric = validate_schema(
                conn, source_ddl, destination_schema
            )
            row_count = validate_rows(conn, columns, dimension)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    return {
        "db_path": str(resolved_db_path),
        "source_table": SOURCE_TABLE,
        "destination_table": DESTINATION_TABLE,
        "source_ddl": source_ddl,
        "destination_ddl": destination_schema,
        "dimension": dimension,
        "distance_metric": distance_metric,
        "row_count": row_count,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create vec_embeddings_v2 as a partition-key-free copy of "
            "vec_embeddings and validate the copy."
        )
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Embeddings SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--extension-path",
        default=DEFAULT_SQLITE_VEC_EXTENSION_PATH,
        help=f"sqlite-vec extension (default: {DEFAULT_SQLITE_VEC_EXTENSION_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        summary = migrate_vec_embeddings_v2(Path(args.db_path), args.extension_path)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Database:    {summary['db_path']}")
    print(f"Source:      {summary['source_table']}")
    print(f"Destination: {summary['destination_table']}")
    print(f"Dimensions:  {summary['dimension']}")
    print(f"Distance:    {summary['distance_metric']}")
    print(f"Rows copied: {summary['row_count']}")
    print(f"Schema:      {summary['destination_ddl']}")
    print("[OK] vec_embeddings_v2 created and validated.")
    print("Source table was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
