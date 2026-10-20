#!/usr/bin/env python3
"""Compare the schemas of two SQLite database files.

Reports tables, columns, indexes, views, and triggers that differ between
two databases, normalized so that only real schema differences show.
Intended for checking whether a database file (for example
episodic-v3.sqlite) matches the schema another one uses (episodic-v2.sqlite).

Usage:
    python scripts/compare_sqlite_schema.py OLD.sqlite NEW.sqlite
    python scripts/compare_sqlite_schema.py OLD.sqlite NEW.sqlite --sql
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Any, Dict, List, Tuple


def _tables(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return {str(name): str(sql or "") for name, sql in rows}


def _columns(conn: sqlite3.Connection, table: str) -> List[Tuple[Any, ...]]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    # (cid, name, type, notnull, dflt_value, pk) -> keep the meaningful parts
    return [(row[1], row[2], bool(row[3]), row[4], bool(row[5])) for row in rows]


def _indexes(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    names = []
    for row in rows:
        # (seq, name, unique, origin, partial); skip auto-indexes
        if row[3] == "c":
            names.append(str(row[1]))
    return sorted(names)


def _index_details(conn: sqlite3.Connection, table: str) -> List[str]:
    details = []
    for name in _indexes(conn, table):
        cols = conn.execute(f"PRAGMA index_info({name})").fetchall()
        col_names = ",".join(str(row[2]) for row in cols)
        details.append(f"{name}({col_names})")
    return sorted(details)


def _foreign_keys(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    return sorted(
        f"{row[3]} -> {row[2]}.{row[4]}" for row in rows
    )  # from_col -> table.to_col


def _views(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'view' ORDER BY name"
    ).fetchall()
    return {str(name): str(sql or "") for name, sql in rows}


def _triggers(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' ORDER BY name"
    ).fetchall()
    return {str(name): str(sql or "") for name, sql in rows}


def _schema(conn: sqlite3.Connection) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"tables": {}, "views": {}, "triggers": {}}
    for table in _tables(conn):
        schema["tables"][table] = {
            "columns": _columns(conn, table),
            "indexes": _index_details(conn, table),
            "foreign_keys": _foreign_keys(conn, table),
            "sql": " ".join((_tables(conn).get(table) or "").split()),
        }
    schema["views"] = {
        name: " ".join(sql.split()) for name, sql in _views(conn).items()
    }
    schema["triggers"] = {
        name: " ".join(sql.split()) for name, sql in _triggers(conn).items()
    }
    return schema


def _describe_column(column: Tuple[Any, ...]) -> str:
    name, ctype, notnull, default, pk = column
    parts = [str(name), str(ctype) or "''"]
    if notnull:
        parts.append("NOT NULL")
    if default is not None:
        parts.append(f"DEFAULT {default}")
    if pk:
        parts.append("PK")
    return " ".join(parts)


def compare(old_path: str, new_path: str, show_sql: bool) -> List[str]:
    old_conn = sqlite3.connect(f"file:{old_path}?mode=ro", uri=True)
    new_conn = sqlite3.connect(f"file:{new_path}?mode=ro", uri=True)
    old, new = _schema(old_conn), _schema(new_conn)
    old_conn.close()
    new_conn.close()

    report: List[str] = []
    for kind in ("tables", "views", "triggers"):
        old_names, new_names = set(old[kind]), set(new[kind])
        for name in sorted(old_names - new_names):
            report.append(f"[-] {kind[:-1]} removed: {name}")
        for name in sorted(new_names - old_names):
            report.append(f"[+] {kind[:-1]} added: {name}")
        for name in sorted(old_names & new_names):
            if old[kind][name] != new[kind][name]:
                report.append(f"[~] {kind[:-1]} changed: {name}")

    for table in sorted(set(old["tables"]) | set(new["tables"])):
        if table not in old["tables"]:
            report.append(f"    [+] {table}: {len(new['tables'][table]['columns'])} columns")
            continue
        if table not in new["tables"]:
            continue
        old_t, new_t = old["tables"][table], new["tables"][table]
        old_cols = {c[0]: c for c in old_t["columns"]}
        new_cols = {c[0]: c for c in new_t["columns"]}
        for col in sorted(set(old_cols) - set(new_cols)):
            report.append(f"[-] {table}.{col} removed ({_describe_column(old_cols[col])})")
        for col in sorted(set(new_cols) - set(old_cols)):
            report.append(f"[+] {table}.{col} added ({_describe_column(new_cols[col])})")
        for col in sorted(set(old_cols) & set(new_cols)):
            if old_cols[col] != new_cols[col]:
                report.append(
                    f"[~] {table}.{col} changed: "
                    f"'{_describe_column(old_cols[col])}' -> '{_describe_column(new_cols[col])}'"
                )
        for label in ("indexes", "foreign_keys"):
            if old_t[label] != new_t[label]:
                report.append(f"[~] {table} {label}: {old_t[label]} -> {new_t[label]}")
        if show_sql and old_t["sql"] != new_t["sql"]:
            report.append(f"    old: {old_t['sql']}")
            report.append(f"    new: {new_t['sql']}")
    return report


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("old", help="Reference database file")
    parser.add_argument("new", help="Database file to compare against it")
    parser.add_argument(
        "--sql", action="store_true",
        help="Also print the raw CREATE statements for changed tables",
    )
    args = parser.parse_args(argv)
    report = compare(args.old, args.new, args.sql)
    if not report:
        print(f"{args.old} and {args.new} have identical schemas.")
        return 0
    print(f"Schema differences ({args.old} -> {args.new}):")
    for line in report:
        print(line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
