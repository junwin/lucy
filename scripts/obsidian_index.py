#!/usr/bin/env python3
"""Canonical CLI entrypoint to index an Obsidian vault into Lucy's document store.

Usage examples:
    python scripts/obsidian_index.py --vault-path docs/minidoc --max-files 1
    python scripts/obsidian_index.py --vault-root /mnt/obsidian --vault-path myvault --dry-run
    # Use a named vault root mapped via env var LUCY_VAULT_ROOT_MYNAME:
    export LUCY_VAULT_ROOT_OBSIDIAN=/mnt/obsidian
    python scripts/obsidian_index.py --vault-root-name obsidian --vault-path myvault

This script is the preferred entrypoint. A lightweight shim remains at
src/obsidian_index_cli.py for backward compatibility.

Guidelines followed here:
- No hard-coded absolute paths. Defaults use the repository root (computed
  from this file) or environment variables.
- Paths that are relative are resolved against the repository root so
  CI/tests do not depend on the current working directory.

New options added:
- --vault-root: optional absolute path to an Obsidian vault root. When
  provided, --vault-path is interpreted relative to this root (vault_path
  may be '.' or a subdirectory).
- --vault-root-name: optional name that maps to an environment variable
  LUCY_VAULT_ROOT_<NAME> (uppercased). If the env var is not set a clear
  error is raised. If both --vault-root and --vault-root-name are provided
  the explicit --vault-root takes precedence.
- --dry-run: print resolved paths and exit without performing indexing.

Validation behaviour:
- If --vault-root (or --vault-root-name) is provided, the user MUST also
  provide an explicit --vault-path. Relying on the script's default vault
  path when a separate vault root is specified is error-prone and therefore
  rejected with a clear message.
"""
from __future__ import annotations

import sys
from pathlib import Path
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import argparse
import logging
import os
import getpass
from typing import Optional

from src.storage.json_file_storage import JsonFileStorage
from src.utils.obsidian_importer import index_obsidian_vault
from src.storage_paths.storage_paths import StoragePaths


def default_storage_root() -> str:
    # Prefer explicit env var, otherwise default to a `data` dir under the repo root.
    return os.environ.get("LUCY_STORAGE_ROOT", str(_repo_root / "data"))


def default_vault_path() -> str:
    # Default vault path is docs/minidoc under the repository root.
    return os.environ.get("LUCY_VAULT_PATH", str(_repo_root / "docs" / "minidoc"))


def _fatal(msg: str, exit_code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Index an Obsidian vault (or subfolder) into Lucy's document store.",
    )

    parser.add_argument(
        "--base-path",
        default=default_storage_root(),
        help=(
            "Storage root path for StoragePaths (can also be set via LUCY_STORAGE_ROOT env var). "
            "Default: '<repo_root>/data'"
        ),
    )
    parser.add_argument(
        "--storage-namespace",
        default=os.environ.get("LUCY_STORAGE_NAMESPACE", "data"),
        help="Storage namespace (subfolder under base-path). Default: 'data'",
    )
    parser.add_argument(
        "--account",
        default=os.environ.get("LUCY_ACCOUNT") or getpass.getuser(),
        help="Account name to associate with the documents (default: current user)",
    )

    # Compute the default vault path now so we can show it in the help text.
    computed_default_vault = default_vault_path()

    # Note: we intentionally do not set a real argparse default here. We want to
    # be able to detect whether the user explicitly passed --vault-path. If a
    # vault root is provided (via --vault-root or --vault-root-name) the user
    # MUST also explicitly pass --vault-path; relying on the script's default
    # vault path in that case is error-prone and rejected.
    parser.add_argument(
        "--vault-path",
        default=argparse.SUPPRESS,
        help=(
            "Path to the Obsidian vault or folder to index. Can be absolute or relative to the repository root. "
            f"Default (when not using --vault-root): {computed_default_vault}"
        ),
    )
    parser.add_argument(
        "--vault-root",
        default=None,
        help=(
            "Optional absolute path to a vault root. When provided, --vault-path is interpreted relative to this root. "
            "If omitted, --vault-path is resolved against the repository root (current behavior)."
        ),
    )
    parser.add_argument(
        "--vault-root-name",
        default=None,
        help=(
            "Optional named vault root. When provided the script looks for an environment variable"
            " LUCY_VAULT_ROOT_<NAME> (uppercased). If the env var is not set a clear error is raised."
        ),
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional maximum number of markdown files to index.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved paths and exit without indexing.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    storage_root = args.base_path
    storage_namespace = args.storage_namespace

    storage_paths = StoragePaths(storage_root, storage_namespace)
    storage = JsonFileStorage(storage_paths)

    # Resolve vault path based on new rules:
    # Detect whether the user provided --vault-path explicitly.
    vault_path_provided = "vault_path" in args.__dict__
    if vault_path_provided:
        vault_path_arg = Path(args.vault_path)
    else:
        # Use the computed default only when the user did not provide a vault_root.
        vault_path_arg = Path(computed_default_vault)

    vault_root: Optional[Path] = None

    if args.vault_root:
        vault_root = Path(args.vault_root)
    elif args.vault_root_name:
        env_key = f"LUCY_VAULT_ROOT_{args.vault_root_name.upper()}"
        vault_root_val = os.environ.get(env_key)
        if vault_root_val:
            vault_root = Path(vault_root_val)
        else:
            _fatal(
                f"Vault root name '{args.vault_root_name}' was provided but environment variable '{env_key}' is not set. "
                "Set the env var or use --vault-root to provide an absolute path."
            )

    # Validation: if a vault_root was provided, require an explicit --vault-path.
    if vault_root and not vault_path_provided:
        _fatal(
            "When --vault-root (or --vault-root-name) is provided you must also supply an explicit --vault-path. "
            "Relying on the script's default vault path when pointing at a separate vault root is unsafe."
        )

    # If a vault_root is provided, interpret vault_path relative to it. vault_path may be '.' or a subdir.
    if vault_root:
        # Ensure vault_root is absolute
        if not vault_root.is_absolute():
            _fatal("--vault-root must be an absolute path")
        vault_root_res = vault_root.resolve()
        # Construct combined path and make sure it does not escape the provided root.
        combined = (vault_root_res / vault_path_arg).resolve()
        try:
            # Will raise ValueError if combined is not under vault_root_res
            combined.relative_to(vault_root_res)
        except ValueError:
            _fatal(
                f"Resolved vault path '{combined}' escapes the provided vault root '{vault_root_res}'. "
                "Ensure --vault-path does not contain '..' or point outside the vault root."
            )
        vault = combined
    else:
        # No vault_root provided: keep current behaviour. If vault_path is absolute, use it; else resolve against repo root.
        vault = vault_path_arg
        if not vault.is_absolute():
            vault = (_repo_root / vault).resolve()

    # Basic validation of final vault path
    if args.dry_run:
        print("DRY RUN: resolved configuration:")
        print(f"  storage_root: {storage_root}")
        print(f"  storage_namespace: {storage_namespace}")
        print(f"  account: {args.account}")
        if vault_root:
            print(f"  vault_root: {vault_root_res}")
        else:
            print(f"  vault_root: (none; resolved against repo root {_repo_root})")
        print(f"  vault_path_arg: {vault_path_arg}")
        print(f"  resolved_vault: {vault}")
        print(f"  exists: {vault.exists()}")
        print(f"  is_dir: {vault.is_dir()}")
        sys.exit(0)

    if not vault.exists():
        _fatal(f"Resolved vault path does not exist: {vault}")
    if not vault.is_dir():
        _fatal(f"Resolved vault path is not a directory: {vault}")

    docs = index_obsidian_vault(
        storage=storage,
        account_name=args.account,
        vault_path=vault,
        max_files=args.max_files,
    )

    print(f"Indexed {len(docs)} documents from {vault} for account {args.account}.")


if __name__ == "__main__":
    main()
