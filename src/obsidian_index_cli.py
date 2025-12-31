from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.storage.json_file_storage import JsonFileStorage
from src.utils.obsidian_importer import index_obsidian_vault


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index an Obsidian vault (or subfolder) into Lucy's document store.",
    )
    parser.add_argument(
        "--base-path",
        default="data",
        help="Base path for JsonFileStorage (default: data)",
    )
    parser.add_argument(
        "--account",
        default="junwin",
        help="Account name to associate with the documents (default: junwin)",
    )
    parser.add_argument(
        "--vault-path",
        default="/home/junwin/src/repos/lucy/docs/minidoc",
        help=(
            "Path to the Obsidian vault or folder to index "
            "(default: /home/junwin/obsidian/test/books)"
        ),
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional maximum number of markdown files to index.",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    base_path = Path(args.base_path).expanduser().resolve()
    storage = JsonFileStorage(str(base_path))

    docs = index_obsidian_vault(
        storage=storage,
        account_name=args.account,
        vault_path=args.vault_path,
        max_files=args.max_files,
    )

    print(f"Indexed {len(docs)} documents from {args.vault_path} for account {args.account}.")


if __name__ == "__main__":
    main()
