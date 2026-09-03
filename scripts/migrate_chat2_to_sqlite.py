#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
from src.chat2.sqlite import (
    SqliteChat2Primitives,
    correlation_key,
    session_events_key,
    session_meta_key,
    sessions_prefix,
)
from src.chat2.store_primitives import StoreKey
from src.config_manager import ConfigManager
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths

PREFIXES = (sessions_prefix().value, "correlations/")
MIGRATED = "migrated"
SKIPPED = "skipped"
IGNORED = "ignored"
ERROR = "error"


@dataclass
class Counters:
    documents: dict = field(
        default_factory=lambda: {MIGRATED: 0, SKIPPED: 0, IGNORED: 0, ERROR: 0}
    )
    logs: dict = field(
        default_factory=lambda: {MIGRATED: 0, SKIPPED: 0, IGNORED: 0, ERROR: 0}
    )
    error_keys: List[str] = field(default_factory=list)
    ignored_keys: List[str] = field(default_factory=list)

    def record(self, category: str, status: str, key: StoreKey) -> None:
        bucket = self.documents if category == "documents" else self.logs
        bucket[status] += 1
        if status == ERROR:
            self.error_keys.append(key.value)
        elif status == IGNORED:
            self.ignored_keys.append(key.value)

    def total(self, status: str) -> int:
        return self.documents[status] + self.logs[status]


def classify(key: StoreKey) -> str:
    return "logs" if key.value.endswith(".jsonl") else "documents"


def is_migratable(key: StoreKey) -> bool:
    parts = key.value.split("/")
    if len(parts) == 3 and parts[0] == sessions_prefix().value.rstrip("/"):
        try:
            return key.value in (
                session_meta_key(parts[1]).value,
                session_events_key(parts[1]).value,
            )
        except ValueError:
            return False
    if len(parts) == 2 and parts[0] == "correlations":
        try:
            return key.value == correlation_key(
                parts[1].removesuffix(".jsonl")
            ).value
        except (TypeError, ValueError):
            return False
    return False


def resolve_config_path(arg: Optional[str]) -> str:
    if arg:
        return arg
    return str(Path(__file__).resolve().parent.parent / "config.json")


def resolve_source_root(config: ConfigManager, override: Optional[str]) -> Path:
    if override:
        return Path(override).resolve()
    root = config.get("storage_root_path") or "/home/junwin/lucydata"
    namespace = config.get("storage_namespace") or "data"
    return Path(root) / namespace / "chat2"


def resolve_db_path(config: ConfigManager, override: Optional[str]) -> Path:
    if override:
        return Path(override).resolve()
    db_path = config.get("chat2_store_db_path")
    if db_path:
        return Path(db_path).resolve()
    root = config.get("storage_root_path") or "/home/junwin/lucydata"
    namespace = config.get("storage_namespace") or "data"
    return Path(root) / namespace / "chat2.sqlite"


def build_source(source_root: Path) -> JfsChat2Primitives:
    if source_root.name != "chat2":
        raise ValueError(
            f"--source-root must point at a directory named 'chat2': {source_root}"
        )
    storage_paths = StoragePaths(
        str(source_root.parent.parent), source_root.parent.name
    )
    return JfsChat2Primitives(JsonFileStorage(storage_paths))


def copy_key(
    source: JfsChat2Primitives,
    dest: SqliteChat2Primitives,
    key: StoreKey,
    dry_run: bool,
) -> str:
    if dest.exists(key):
        return SKIPPED
    if classify(key) == "logs":
        lines = source.read_lines(key)
        if lines is None:
            if not dry_run:
                dest.write_text(key, "")
        elif not dry_run:
            dest.append_lines(key, lines)
    else:
        text = source.read_text(key)
        if text is None:
            return ERROR
        if not dry_run:
            dest.write_text(key, text)
    return MIGRATED


def migrate(
    source: JfsChat2Primitives,
    dest: SqliteChat2Primitives,
    dry_run: bool,
    verbose: bool,
) -> Counters:
    counters = Counters()
    for prefix in PREFIXES:
        keys = sorted(source.list_keys(StoreKey(prefix)), key=lambda k: k.value)
        for key in keys:
            if not is_migratable(key):
                counters.record(classify(key), IGNORED, key)
                continue
            if verbose:
                print(f"  {key.value}")
            status = copy_key(source, dest, key, dry_run)
            counters.record(classify(key), status, key)
    return counters


def verify(
    source: JfsChat2Primitives,
    dest: SqliteChat2Primitives,
    keys: List[StoreKey],
) -> List[str]:
    mismatches: List[str] = []
    for key in keys:
        if classify(key) == "logs":
            expected = source.read_lines(key)
            if expected is None:
                if dest.read_text(key) is None:
                    mismatches.append(f"{key.value}: missing in destination")
            elif dest.read_lines(key) != expected:
                mismatches.append(f"{key.value}: log lines differ")
        elif dest.read_text(key) != source.read_text(key):
            mismatches.append(f"{key.value}: document differs")
    return mismatches


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate chat2 JSONL store into the SQLite chat2 store"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Config file (config.local.json merged automatically)",
    )
    parser.add_argument(
        "--source-root",
        default=None,
        help="chat2 JSONL root (default: <storage_root>/<namespace>/chat2)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite db path (default: <storage_root>/<namespace>/chat2.sqlite)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    config = ConfigManager(resolve_config_path(args.config))
    source_root = resolve_source_root(config, args.source_root)
    db_path = resolve_db_path(config, args.db_path)

    if not source_root.exists():
        print(f"[ERROR] source root does not exist: {source_root}")
        return 1

    source = build_source(source_root)
    dest = SqliteChat2Primitives(str(db_path))
    try:
        print(f"Source: JfsChat2Primitives({source_root})")
        print(f"Target: SqliteChat2Primitives({db_path})")
        print(f"Mode:   {'dry-run' if args.dry_run else 'migrate'}")

        dest_before = {
            prefix: set(k.value for k in dest.list_keys(StoreKey(prefix)))
            for prefix in PREFIXES
        }
        migratable_keys: List[StoreKey] = []
        for prefix in PREFIXES:
            prefix_keys = [
                key
                for key in source.list_keys(StoreKey(prefix))
                if is_migratable(key)
            ]
            migratable_keys.extend(prefix_keys)
            print(
                f"  {prefix}: source={len(prefix_keys)} "
                f"target_before={len(dest_before[prefix])}"
            )

        session_docs = 0
        session_logs = 0
        correlation_logs = 0
        for key in migratable_keys:
            if key.value.startswith(sessions_prefix().value):
                if classify(key) == "documents":
                    session_docs += 1
                else:
                    session_logs += 1
            else:
                correlation_logs += 1

        counters = migrate(source, dest, dry_run=args.dry_run, verbose=args.verbose)

        print(f"sessions: {session_docs} documents, {session_logs} event logs")
        print(f"correlations: {correlation_logs} logs")
        print(f"documents: {counters.documents}")
        print(f"logs:      {counters.logs}")
        print(
            f"total: migrated={counters.total(MIGRATED)} "
            f"skipped={counters.total(SKIPPED)} "
            f"ignored={counters.total(IGNORED)} "
            f"errors={counters.total(ERROR)}"
        )
        if counters.ignored_keys:
            print("ignored keys:")
            for key in counters.ignored_keys:
                print(f"  {key}")
        if counters.error_keys:
            print("[ERROR] failed keys:")
            for key in counters.error_keys:
                print(f"  {key}")
            return 1

        if args.dry_run:
            print("[DRY-RUN] nothing was written.")
            return 0

        mismatches = verify(source, dest, migratable_keys)
        if mismatches:
            print("[ERROR] verification mismatches:")
            for item in mismatches:
                print(f"  {item}")
            return 1

        for prefix in PREFIXES:
            source_keys = {
                key.value
                for key in source.list_keys(StoreKey(prefix))
                if is_migratable(key)
            }
            expected = dest_before[prefix] | source_keys
            actual = set(k.value for k in dest.list_keys(StoreKey(prefix)))
            print(f"  {prefix}: target_after={len(actual)}")
            if actual != expected:
                print(
                    f"[ERROR] count verification failed for {prefix}: "
                    f"expected {len(expected)} keys, got {len(actual)}"
                )
                missing = sorted(expected - actual)
                extra = sorted(actual - expected)
                if missing:
                    print(f"  missing: {missing[:10]}")
                if extra:
                    print(f"  extra: {extra[:10]}")
                return 1

        source_rows = 0
        dest_rows = 0
        for key in migratable_keys:
            if classify(key) == "logs":
                source_lines = source.read_lines(key)
                dest_lines = dest.read_lines(key)
                source_rows += len(source_lines) if source_lines else 0
                dest_rows += len(dest_lines) if dest_lines else 0
        print(f"log rows: source={source_rows} dest={dest_rows}")

        print("Verification: OK")
    finally:
        dest.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
