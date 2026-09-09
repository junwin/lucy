#!/usr/bin/env python3
"""Copy a legacy Lucy sqlite-vec store into the canonical vec0 schema.

This migration is deliberately *not* an in-place schema upgrade. The source
SQLite database is opened read-only and is never modified. Records are copied
into a new destination database created by ``Vec0EmbeddingStore``.

The script follows the canonical-schema migration rules:

* preserve vectors exactly; never call an embedding provider;
* preserve account/namespace/source refs/metadata/timestamps;
* preserve record IDs that are already valid UUIDs;
* require explicit ``--assign-new-uuids`` before replacing legacy IDs;
* promote ``source_metadata.content_hash`` to ``document_id`` only when the
  hash can be verified against the raw source file, unless the operator
  explicitly supplies ``--trust-content-hash``;
* never invent model/provider provenance. Existing metadata may supply it, or
  the operator may explicitly assert it with ``--model`` / ``--provider``;
* validate counts, metadata and representative recall/filter behaviour before
  reporting success.

Typical use::

    python scripts/migrate_vec0_canonical.py \
        --source /path/embeddings.sqlite \
        --destination /path/embeddings-v2.sqlite \
        --dry-run

    python scripts/migrate_vec0_canonical.py \
        --source /path/embeddings.sqlite \
        --destination /path/embeddings-v2.sqlite \
        --assign-new-uuids \
        --model text-embedding-3-small \
        --provider openai

The destination must not already exist. Switching Lucy to the new database is
an explicit operational step outside this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import struct
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.models import EmbeddingRecord
from src.storage.vec0_embedding_store import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    Vec0EmbeddingStore,
)

_EMBEDDING_DIM = 1536
_REQUIRED_LEGACY_METADATA_COLUMNS = {
    "id",
    "account_name",
    "namespace",
    "source_type",
    "source_id",
    "source_metadata",
    "created_at",
}


@dataclass(frozen=True)
class LegacyRecord:
    id: str
    account_name: str
    namespace: str
    vector: List[float]
    source_type: str
    source_id: str
    source_metadata: Dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class PreparedRecord:
    record: EmbeddingRecord
    old_id: str
    id_replaced: bool
    document_id_verified: bool
    provenance_known: bool


def _load_vec_extension(conn: sqlite3.Connection, extension_path: str) -> None:
    conn.enable_load_extension(True)
    conn.load_extension(extension_path)


def _open_source_read_only(path: Path, extension_path: str) -> sqlite3.Connection:
    # URI mode=ro gives us an OS/SQLite-level guard against accidental writes.
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    _load_vec_extension(conn, extension_path)
    return conn


def _decode_vector(blob: bytes) -> List[float]:
    if len(blob) % 4:
        raise ValueError(f"invalid float32 vector blob length: {len(blob)}")
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _parse_created_at(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("embedding record has empty created_at")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _require_legacy_schema(conn: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    }
    missing_tables = {"vec_embeddings", "embedding_metadata"} - tables
    if missing_tables:
        raise ValueError(
            "source is not a Lucy vec0 store; missing table(s): "
            + ", ".join(sorted(missing_tables))
        )

    metadata_columns = _table_columns(conn, "embedding_metadata")
    missing_columns = _REQUIRED_LEGACY_METADATA_COLUMNS - metadata_columns
    if missing_columns:
        raise ValueError(
            "source embedding_metadata is missing required legacy column(s): "
            + ", ".join(sorted(missing_columns))
        )


def _read_legacy_records(conn: sqlite3.Connection) -> List[LegacyRecord]:
    _require_legacy_schema(conn)

    duplicate_ids = conn.execute(
        "SELECT id, COUNT(*) FROM vec_embeddings GROUP BY id HAVING COUNT(*) > 1"
    ).fetchall()
    if duplicate_ids:
        preview = ", ".join(f"{record_id!r} x{count}" for record_id, count in duplicate_ids[:5])
        raise ValueError(
            "source vec_embeddings contains duplicate record IDs; refusing ambiguous migration: "
            + preview
        )

    orphan_vectors = conn.execute(
        "SELECT COUNT(*) FROM vec_embeddings v LEFT JOIN embedding_metadata m ON m.id = v.id"
        " WHERE m.id IS NULL"
    ).fetchone()[0]
    orphan_metadata = conn.execute(
        "SELECT COUNT(*) FROM embedding_metadata m LEFT JOIN vec_embeddings v ON v.id = m.id"
        " WHERE v.id IS NULL"
    ).fetchone()[0]
    if orphan_vectors or orphan_metadata:
        raise ValueError(
            "source store is inconsistent: "
            f"{orphan_vectors} vector row(s) lack metadata and "
            f"{orphan_metadata} metadata row(s) lack vectors"
        )

    rows = conn.execute(
        "SELECT m.id, m.account_name, m.namespace, v.embedding, m.source_type,"
        " m.source_id, m.source_metadata, m.created_at"
        " FROM embedding_metadata m JOIN vec_embeddings v ON v.id = m.id"
        " ORDER BY m.account_name, m.namespace, m.id"
    ).fetchall()

    records: List[LegacyRecord] = []
    for row in rows:
        vector = _decode_vector(row[3])
        if len(vector) != _EMBEDDING_DIM:
            raise ValueError(
                f"record {row[0]!r} has {len(vector)} dimensions; expected {_EMBEDDING_DIM}"
            )
        try:
            metadata = json.loads(row[6] or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"record {row[0]!r} has invalid source_metadata JSON") from exc
        if not isinstance(metadata, dict):
            raise ValueError(f"record {row[0]!r} source_metadata must be a JSON object")

        records.append(
            LegacyRecord(
                id=str(row[0]),
                account_name=str(row[1]),
                namespace=str(row[2]),
                vector=vector,
                source_type=str(row[4] or ""),
                source_id=str(row[5] or ""),
                source_metadata=metadata,
                created_at=_parse_created_at(row[7]),
            )
        )
    return records


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text)


def _resolve_document_id(
    metadata: Dict[str, Any], *, trust_content_hash: bool
) -> Tuple[str, bool]:
    candidate = metadata.get("content_hash")
    if not _looks_like_sha256(candidate):
        return "", False
    candidate = str(candidate).lower()

    if trust_content_hash:
        return candidate, True

    path_value = metadata.get("path")
    if not path_value:
        return "", False
    source_path = Path(str(path_value)).expanduser()
    if not source_path.is_file():
        return "", False
    try:
        actual = _sha256_file(source_path)
    except OSError:
        return "", False
    if actual == candidate:
        return candidate, True
    return "", False


def _first_nonempty(metadata: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _resolve_provenance(
    metadata: Dict[str, Any], *, asserted_model: str, asserted_provider: str
) -> Tuple[str, str, bool]:
    model = asserted_model.strip() or _first_nonempty(
        metadata, ("embedding_model", "model")
    )
    provider = asserted_provider.strip() or _first_nonempty(
        metadata, ("embedding_provider", "provider")
    )
    return model, provider, bool(model and provider)


def prepare_records(
    records: Iterable[LegacyRecord],
    *,
    assign_new_uuids: bool,
    trust_content_hash: bool,
    model: str,
    provider: str,
) -> List[PreparedRecord]:
    prepared: List[PreparedRecord] = []
    assigned_ids: set[str] = set()

    for legacy in records:
        id_replaced = not _is_uuid(legacy.id)
        if id_replaced:
            if not assign_new_uuids:
                new_id = legacy.id
            else:
                new_id = str(uuid.uuid4())
        else:
            new_id = legacy.id

        if new_id in assigned_ids:
            raise ValueError(f"migration would create duplicate id {new_id!r}")
        assigned_ids.add(new_id)

        document_id, document_id_verified = _resolve_document_id(
            legacy.source_metadata, trust_content_hash=trust_content_hash
        )
        resolved_model, resolved_provider, provenance_known = _resolve_provenance(
            legacy.source_metadata,
            asserted_model=model,
            asserted_provider=provider,
        )

        prepared.append(
            PreparedRecord(
                old_id=legacy.id,
                id_replaced=id_replaced,
                document_id_verified=document_id_verified,
                provenance_known=provenance_known,
                record=EmbeddingRecord(
                    id=new_id,
                    account_name=legacy.account_name,
                    namespace=legacy.namespace,
                    vector=list(legacy.vector),
                    source_type=legacy.source_type,
                    source_id=legacy.source_id,
                    source_metadata=dict(legacy.source_metadata),
                    created_at=legacy.created_at,
                    document_id=document_id,
                    model=resolved_model,
                    provider=resolved_provider,
                    dimensions=len(legacy.vector),
                ),
            )
        )
    return prepared


def _summary(prepared: Sequence[PreparedRecord]) -> Dict[str, Any]:
    namespaces = Counter(
        (item.record.account_name, item.record.namespace) for item in prepared
    )
    source_types = Counter(item.record.source_type for item in prepared)
    return {
        "records": len(prepared),
        "valid_uuid_ids": sum(not item.id_replaced for item in prepared),
        "ids_requiring_assignment": sum(item.id_replaced for item in prepared),
        "verified_document_ids": sum(item.document_id_verified for item in prepared),
        "requires_source_rescan": sum(not item.document_id_verified for item in prepared),
        "known_provenance": sum(item.provenance_known for item in prepared),
        "unknown_provenance": sum(not item.provenance_known for item in prepared),
        "namespaces": {
            f"{account}/{namespace}": count
            for (account, namespace), count in sorted(namespaces.items())
        },
        "source_types": dict(sorted(source_types.items())),
    }


def _write_destination(
    destination: Path,
    prepared: Sequence[PreparedRecord],
    extension_path: str,
) -> None:
    if destination.exists():
        raise FileExistsError(
            f"destination already exists; refusing to overwrite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Vec0EmbeddingStore(str(destination), extension_path) as store:
            for item in prepared:
                store.upsert_embedding(item.record)
    except BaseException:
        # A partially-created destination must never masquerade as an accepted
        # migration. Best effort cleanup leaves the source untouched.
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _canonical_rows(
    destination: Path, extension_path: str
) -> Dict[str, Tuple[Any, ...]]:
    conn = sqlite3.connect(str(destination))
    try:
        _load_vec_extension(conn, extension_path)
        rows = conn.execute(
            "SELECT id, account_name, namespace, source_type, source_id, document_id,"
            " model, provider, dimensions, source_metadata, created_at"
            " FROM embedding_metadata ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return {str(row[0]): tuple(row) for row in rows}


def validate_destination(
    destination: Path,
    prepared: Sequence[PreparedRecord],
    extension_path: str,
) -> List[str]:
    errors: List[str] = []
    rows = _canonical_rows(destination, extension_path)
    if len(rows) != len(prepared):
        errors.append(
            f"metadata count mismatch: expected {len(prepared)}, got {len(rows)}"
        )

    expected_by_id = {item.record.id: item.record for item in prepared}
    if set(rows) != set(expected_by_id):
        missing = sorted(set(expected_by_id) - set(rows))
        extra = sorted(set(rows) - set(expected_by_id))
        if missing:
            errors.append(f"destination missing id(s): {missing[:5]}")
        if extra:
            errors.append(f"destination has unexpected id(s): {extra[:5]}")

    for record_id in set(rows) & set(expected_by_id):
        row = rows[record_id]
        expected = expected_by_id[record_id]
        actual_metadata = json.loads(row[9] or "{}")
        checks = (
            (row[1], expected.account_name, "account_name"),
            (row[2], expected.namespace, "namespace"),
            (row[3], expected.source_type, "source_type"),
            (row[4], expected.source_id, "source_id"),
            (row[5], expected.document_id, "document_id"),
            (row[6], expected.model, "model"),
            (row[7], expected.provider, "provider"),
            (row[8], expected.dimensions, "dimensions"),
            (actual_metadata, expected.source_metadata, "source_metadata"),
        )
        for actual, wanted, field in checks:
            if actual != wanted:
                errors.append(f"{record_id}: {field} mismatch")
                break

    conn = sqlite3.connect(str(destination))
    try:
        _load_vec_extension(conn, extension_path)
        vec_count = conn.execute("SELECT COUNT(*) FROM vec_embeddings").fetchone()[0]
    finally:
        conn.close()
    if vec_count != len(prepared):
        errors.append(
            f"vector count mismatch: expected {len(prepared)}, got {vec_count}"
        )

    # Exercise the actual store query path for one representative record per
    # account/namespace/source_type. The record's own vector should retrieve at
    # least one result under the same pre-top-k filters.
    representatives: Dict[Tuple[str, str, str], EmbeddingRecord] = {}
    for item in prepared:
        key = (
            item.record.account_name,
            item.record.namespace,
            item.record.source_type,
        )
        representatives.setdefault(key, item.record)

    with Vec0EmbeddingStore(str(destination), extension_path) as store:
        for (account, namespace, source_type), record in representatives.items():
            hits = store.query_embeddings(
                [namespace],
                account,
                record.vector,
                top_k=1,
                filter={"source_type": source_type},
            )
            if not hits:
                errors.append(
                    "filtered recall returned no result for "
                    f"{account}/{namespace}/{source_type}"
                )

    return errors


def migrate_vec0_canonical(
    source: Path,
    destination: Path,
    extension_path: str,
    *,
    dry_run: bool = False,
    assign_new_uuids: bool = False,
    trust_content_hash: bool = False,
    model: str = "",
    provider: str = "",
) -> Dict[str, Any]:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()

    if source == destination:
        raise ValueError("source and destination must be different files")
    if not source.is_file():
        raise FileNotFoundError(f"source database does not exist: {source}")
    if destination.exists():
        raise FileExistsError(
            f"destination already exists; refusing to overwrite: {destination}"
        )

    conn = _open_source_read_only(source, extension_path)
    try:
        legacy = _read_legacy_records(conn)
    finally:
        conn.close()

    prepared = prepare_records(
        legacy,
        assign_new_uuids=assign_new_uuids,
        trust_content_hash=trust_content_hash,
        model=model,
        provider=provider,
    )
    summary = _summary(prepared)
    summary.update(
        {
            "source": str(source),
            "destination": str(destination),
            "dry_run": dry_run,
            "validated": False,
            "validation_errors": [],
        }
    )

    invalid_ids = summary["ids_requiring_assignment"]
    if not dry_run and invalid_ids and not assign_new_uuids:
        raise ValueError(
            f"{invalid_ids} record id(s) are not UUIDs; rerun with "
            "--assign-new-uuids after reviewing the dry-run report"
        )

    if dry_run:
        return summary

    _write_destination(destination, prepared, extension_path)
    errors = validate_destination(destination, prepared, extension_path)
    summary["validation_errors"] = errors
    summary["validated"] = not errors
    return summary


def _print_summary(summary: Dict[str, Any]) -> None:
    print(f"Records found:                  {summary['records']}")
    print(f"Valid UUID IDs:                 {summary['valid_uuid_ids']}")
    print(f"IDs requiring UUID assignment: {summary['ids_requiring_assignment']}")
    print(f"Verified document SHA-256:      {summary['verified_document_ids']}")
    print(f"Requires source rescan:         {summary['requires_source_rescan']}")
    print(f"Known embedding provenance:     {summary['known_provenance']}")
    print(f"Unknown provenance:             {summary['unknown_provenance']}")
    print("Namespaces:")
    for name, count in summary["namespaces"].items():
        print(f"  {name}: {count}")
    print("Source types:")
    for name, count in summary["source_types"].items():
        print(f"  {name or '<empty>'}: {count}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copy a legacy Lucy sqlite-vec store into the canonical vec0 schema"
    )
    parser.add_argument("--source", required=True, help="Existing legacy vec0 SQLite DB")
    parser.add_argument(
        "--destination", required=True, help="New canonical SQLite DB (must not exist)"
    )
    parser.add_argument(
        "--extension-path",
        default=DEFAULT_SQLITE_VEC_EXTENSION_PATH,
        help="Path to sqlite-vec loadable extension",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Inspect and report; write nothing"
    )
    parser.add_argument(
        "--assign-new-uuids",
        action="store_true",
        help="Replace legacy non-UUID record IDs with newly generated UUID4 IDs",
    )
    parser.add_argument(
        "--trust-content-hash",
        action="store_true",
        help=(
            "Treat 64-hex source_metadata.content_hash values as raw-byte SHA-256 "
            "without verifying the referenced source file"
        ),
    )
    parser.add_argument(
        "--model",
        default="",
        help="Explicitly assert one embedding model for records lacking provenance",
    )
    parser.add_argument(
        "--provider",
        default="",
        help="Explicitly assert one embedding provider for records lacking provenance",
    )
    args = parser.parse_args(argv)

    if not Path(args.extension_path).exists():
        print(f"[ERROR] sqlite-vec extension not found: {args.extension_path}")
        return 1

    try:
        summary = migrate_vec0_canonical(
            Path(args.source),
            Path(args.destination),
            args.extension_path,
            dry_run=args.dry_run,
            assign_new_uuids=args.assign_new_uuids,
            trust_content_hash=args.trust_content_hash,
            model=args.model,
            provider=args.provider,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Source:      {summary['source']}")
    print(f"Destination: {summary['destination']}")
    _print_summary(summary)

    if summary["dry_run"]:
        print("[DRY-RUN] No files were written.")
        if summary["ids_requiring_assignment"]:
            print(
                "[ACTION] Review legacy IDs; actual migration requires "
                "--assign-new-uuids."
            )
        return 0

    if not summary["validated"]:
        print("[ERROR] destination validation failed:")
        for error in summary["validation_errors"]:
            print(f"  {error}")
        print("Source database was not modified. Do not switch Lucy to this destination.")
        return 2

    print("[OK] canonical destination created and validated.")
    print("Source database was not modified.")
    print("No config/database switch was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
