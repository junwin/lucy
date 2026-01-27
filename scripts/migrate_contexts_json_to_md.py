#!/usr/bin/env python3
"""
migrate_contexts_json_to_md.py

Convert context files stored as JSON under data/contexts/<account>/*.json into
Markdown files with YAML frontmatter. The YAML frontmatter will contain the
context 'id' and 'account_name' (from the JSON top-level) plus the keys from
context.data except for 'text'. The Markdown body will contain the original
data['text'] (or empty string).

Notes:
- The script writes a new file with the same stem but .md extension next to the
  original .json file.
- By default the original .json files are removed after successful conversion.
  You can pass --keep-original to prevent deletion.
- Use --overwrite to replace an existing .md file.
- This script is idempotent: if an .md file exists and --overwrite is not set,
  the JSON file will be left untouched.
- Use --dry-run to preview actions without writing files.

This script assumes the repository layout where contexts live under
data/contexts/<account>/*.json by default. You can override the contexts root
explicitly with --contexts-root, or set a storage base path and namespace via
--base-path and --storage-namespace (or the LUCY_STORAGE_ROOT / LUCY_STORAGE_NAMESPACE
environment variables). When using --base-path, the contexts root will be
constructed as: <base-path>/<storage-namespace>/contexts (or <base-path>/contexts
if no storage-namespace is provided).

Usage examples:
  python scripts/migrate_contexts_json_to_md.py --dry-run
  python scripts/migrate_contexts_json_to_md.py --overwrite
  python scripts/migrate_contexts_json_to_md.py --keep-original
  python scripts/migrate_contexts_json_to_md.py --overwrite --contexts-root /path/to/data/contexts
  python scripts/migrate_contexts_json_to_md.py --base-path /mnt/lucy_storage --storage-namespace data

There is a small built-in self-check you can run with --self-test which will
create temporary files and verify basic conversion behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
import sys
import yaml


def convert_file(json_path: Path, overwrite: bool = False, remove_original: bool = True, dry_run: bool = False) -> bool:
    """Convert a single JSON context file to a .md file with YAML frontmatter.

    Returns True if conversion was performed (or would be performed in dry_run),
    False if skipped (e.g. .md exists and not overwriting) or on error.
    """
    if not json_path.exists():
        print(f"[WARN] JSON file not found: {json_path}")
        return False

    md_path = json_path.with_suffix('.md')

    if md_path.exists() and not overwrite:
        print(f"[SKIP] Markdown already exists: {md_path} (use --overwrite to replace)")
        return False

    # load json
    try:
        with json_path.open('r', encoding='utf-8') as f:
            obj = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load JSON {json_path}: {e}")
        return False

    # expected shape: {id, account_name, data}
    if not isinstance(obj, dict):
        print(f"[WARN] Unexpected JSON shape (not an object) in {json_path}; skipping")
        return False

    data = obj.get('data')
    if data is None or not isinstance(data, dict):
        print(f"[WARN] Unexpected JSON shape (missing data dict) in {json_path}; skipping")
        return False

    # Extract text body
    text = data.get('text', '')

    # Build frontmatter: include top-level id and account_name, plus data keys except 'text'
    front = {}
    if 'id' in obj:
        front['id'] = obj.get('id')
    if 'account_name' in obj:
        front['account_name'] = obj.get('account_name')

    for k, v in data.items():
        if k == 'text':
            continue
        # Special handling for tasklist: if it's a JSON string representing a mapping,
        # decode it so YAML emits a mapping instead of a JSON-encoded string.
        if k == 'tasklist' and isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    v = parsed
                else:
                    # keep as original if not a mapping; emit a warning
                    print(f"[WARN] tasklist in {json_path} parsed to {type(parsed).__name__}; expected mapping; leaving as-is")
            except Exception:
                # not JSON or failed to parse; leave as-is but warn
                print(f"[WARN] tasklist in {json_path} appears to be a string but not valid JSON; leaving as-is")
        front[k] = v

    # Build YAML frontmatter
    try:
        yaml_front = yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"[ERROR] Failed to serialize YAML for {json_path}: {e}")
        return False

    md_content = "---\n" + (yaml_front or '') + "---\n\n" + (text or '')

    if dry_run:
        print(f"[DRY-RUN] Would write: {md_path}")
        return True

    # Ensure directory exists
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to tmp file then replace
    tmp_path = md_path.with_suffix(md_path.suffix + '.tmp')
    try:
        with tmp_path.open('w', encoding='utf-8') as f:
            f.write(md_content)
        os.replace(tmp_path, md_path)
        print(f"[OK] Wrote {md_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write {md_path}: {e}")
        # cleanup tmp if exists
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return False

    if remove_original:
        try:
            json_path.unlink()
            print(f"[OK] Removed original JSON: {json_path}")
        except Exception as e:
            print(f"[WARN] Failed to remove original JSON {json_path}: {e}")

    return True


def find_json_context_files(base_dir: Path) -> list[Path]:
    """Return all .json files under base_dir/<account>/*.json (non-recursive per account).
    Skip files named "index.json".
    """
    results = []
    if not base_dir.exists():
        return results
    for account_dir in base_dir.iterdir():
        if not account_dir.is_dir():
            continue
        for p in account_dir.glob('*.json'):
            if p.name == 'index.json':
                continue
            results.append(p)
    return results


def _self_test() -> bool:
    """Run a small self-check using temporary files and return True on success.

    This will not touch repository files; it creates temporary account/id.json
    files in a temporary directory and verifies that conversion produces the
    expected .md files and that frontmatter contains id and account_name and
    that tasklist JSON strings are parsed into mappings.
    """
    import textwrap

    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / 'data' / 'contexts'
        account = base / 'alice'
        account.mkdir(parents=True)

        # Case 1: tasklist as JSON string, text present
        obj1 = {
            'id': 'ctx1',
            'account_name': 'alice',
            'data': {
                'text': 'Hello world',
                'title': 'Greeting',
                'tasklist': json.dumps({'done': False, 'items': ['a', 'b']})
            }
        }
        p1 = account / 'ctx1.json'
        p1.write_text(json.dumps(obj1), encoding='utf-8')

        # Case 2: tasklist as dict, no text
        obj2 = {
            'id': 'ctx2',
            'account_name': 'alice',
            'data': {
                'title': 'NoBody',
                'tasklist': {'x': 1}
            }
        }
        p2 = account / 'ctx2.json'
        p2.write_text(json.dumps(obj2), encoding='utf-8')

        # Run conversions
        ok1 = convert_file(p1, overwrite=False, remove_original=True, dry_run=False)
        ok2 = convert_file(p2, overwrite=False, remove_original=True, dry_run=False)

        if not (ok1 and ok2):
            print('[SELF-TEST] Conversion failed')
            return False

        md1 = p1.with_suffix('.md')
        md2 = p2.with_suffix('.md')
        if not md1.exists() or not md2.exists():
            print('[SELF-TEST] Output .md missing')
            return False

        # Read md1 and assert frontmatter has id/account_name and tasklist mapping
        content1 = md1.read_text(encoding='utf-8')
        if 'id: ctx1' not in content1 or 'account_name: alice' not in content1:
            print('[SELF-TEST] Missing id/account_name in frontmatter')
            return False
        if 'tasklist:' not in content1:
            print('[SELF-TEST] Missing tasklist in frontmatter')
            return False
        if 'Hello world' not in content1:
            print('[SELF-TEST] Body text missing')
            return False

        # Ensure original JSON files were removed
        if p1.exists() or p2.exists():
            print('[SELF-TEST] Original JSON files were not removed')
            return False

        print('[SELF-TEST] Passed')
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate context JSON files to Markdown with YAML frontmatter")
    parser.add_argument('--contexts-root', default=None, help='Path to contexts root (default: <base-path>/<storage-namespace>/contexts or <base-path>/contexts if no namespace)')
    parser.add_argument('--base-path', default=os.environ.get('LUCY_STORAGE_ROOT', 'data'), help='Storage base path (can also be set via LUCY_STORAGE_ROOT env var). Default: data')
    parser.add_argument('--storage-namespace', default=os.environ.get('LUCY_STORAGE_NAMESPACE', ''), help='Storage namespace under base-path (optional)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing .md files')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--remove-original', dest='remove_original', action='store_true', help='Remove the original .json files after successful conversion (default)')
    group.add_argument('--keep-original', dest='remove_original', action='store_false', help='Keep the original .json files (opposite of --remove-original)')
    parser.set_defaults(remove_original=True)

    parser.add_argument('--dry-run', action='store_true', help='Do not write files; just show what would be done')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--self-test', action='store_true', help='Run a built-in self-check and exit')

    args = parser.parse_args(argv)

    if args.self_test:
        success = _self_test()
        return 0 if success else 2

    # Determine contexts root. Priority:
    # 1) --contexts-root explicit
    # 2) derive from --base-path and --storage-namespace: <base-path>/<storage-namespace>/contexts
    # 3) fallback to <base-path>/contexts
    if args.contexts_root:
        base = Path(args.contexts_root)
    else:
        base_path = Path(args.base_path)
        if args.storage_namespace:
            base = base_path / args.storage_namespace / 'contexts'
        else:
            base = base_path / 'contexts'

    files = find_json_context_files(base)
    if not files:
        print(f"No JSON context files found under {base}")
        return 0

    performed = 0
    for p in sorted(files):
        if args.verbose:
            print(f"Processing: {p}")
        ok = convert_file(p, overwrite=args.overwrite, remove_original=args.remove_original, dry_run=args.dry_run)
        if ok:
            performed += 1

    print(f"Done. Converted {performed}/{len(files)} files.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
