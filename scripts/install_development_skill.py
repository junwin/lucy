#!/usr/bin/env python3
"""Install the bundled development skill into Lucy's account skill storage."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from galet_memory import FileContextRepository, ProceduralLayout
from src.config_manager import ConfigManager
from src.storage_paths.storage_paths import StoragePaths


def read_skill(path: Path):
    sections = path.read_text(encoding="utf-8").split("---", 2)
    if len(sections) != 3 or sections[0].strip():
        raise ValueError(f"Invalid skill frontmatter: {path}")
    return yaml.safe_load(sections[1]), sections[2].strip() + "\n"


def install(config, accounts: list[str], overwrite: bool = False) -> list[Path]:
    frontmatter, body = read_skill(REPO_ROOT / "static/data/skills/development.md")
    paths = StoragePaths(storage_root_path=config.get("storage_root_path") or "/home/junwin/lucydata",
                         storage_namespace=config.get("storage_namespace") or "data")
    repository = FileContextRepository(paths.base, ProceduralLayout.lucy())
    installed = []
    for account in accounts:
        account = account.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", account):
            raise ValueError("Account names must contain only letters, numbers, dots, underscores or hyphens")
        destination = Path(paths.base) / "skills" / account / "development.md"
        if destination.exists() and not overwrite:
            if read_skill(destination) != (frontmatter, body):
                raise FileExistsError(f"Preserving existing skill: {destination}. Review it before using --overwrite.")
        else:
            repository.save_skill(account_name=account, skill_name="development",
                                  text=body, frontmatter=frontmatter)
        installed.append(destination)
    return installed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", action="append", required=True,
                        help="Account using Star/Colin; repeat for multiple accounts")
    parser.add_argument("--config", default=str(REPO_ROOT / "config.json"))
    parser.add_argument("--overwrite", action="store_true", help="Replace a reviewed existing development skill")
    args = parser.parse_args()
    try:
        for destination in install(ConfigManager(args.config), args.account, args.overwrite):
            print(destination)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
