from __future__ import annotations

# Ensure repo root is on sys.path so the "src" package can be imported when
# running this file directly (python src/obsidian_index_cli.py).
import sys
from pathlib import Path as _Path
_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import argparse
import logging
import os
import getpass
from pathlib import Path
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


def main(argv: Optional[list[str]] = None) -> None:
    """Index an Obsidian vault into Lucy's document store.

    Note: scripts/obsidian_index.py is the canonical CLI entrypoint. This
    module remains for backward compatibility but is considered deprecated.
    Prefer running:

        python scripts/obsidian_index.py --vault-path docs/minidoc --max-files 1

    This function still performs the indexing to avoid breaking callers that
    import and call it directly.
    """
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
    parser.add_argument(
        "--vault-path",
        default=default_vault_path(),
        help=(
            "Path to the Obsidian vault or folder to index. Can be absolute or relative to the repository root. "
            "Default: docs/minidoc under the repo root"
        ),
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional maximum number of markdown files to index.",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # Warn about deprecation but continue for backward compatibility.
    logging.warning(
        "'src.obsidian_index_cli' is deprecated. Use 'python scripts/obsidian_index.py' as the canonical entrypoint."
    )

    # Determine storage root and namespace. Allow env vars to override CLI defaults.
    storage_root = args.base_path
    storage_namespace = args.storage_namespace

    storage_paths = StoragePaths(storage_root, storage_namespace)
    storage = JsonFileStorage(storage_paths)

    # Resolve vault path: if relative, treat as relative to the repository root
    vault = Path(args.vault_path)
    if not vault.is_absolute():
        vault = (_repo_root / vault).resolve()

    docs = index_obsidian_vault(
        storage=storage,
        account_name=args.account,
        vault_path=vault,
        max_files=args.max_files,
    )

    print(f"Indexed {len(docs)} documents from {vault} for account {args.account}.")


if __name__ == "__main__":
    main()
