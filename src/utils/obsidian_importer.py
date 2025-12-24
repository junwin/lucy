from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

import yaml  # type: ignore

from src.storage.base import Storage
from src.storage.models import DocumentRef


def _stable_doc_id_from_path(path: Path) -> str:
    """Create a stable ID from a file path.

    This lets us re-run the importer without creating duplicate documents.
    """
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _extract_title(md_path: Path, contents: Optional[str] = None) -> str:
    """Derive a title from the file.

    For now we just use the stem (filename without extension). Later we could
    parse the first markdown heading.
    """
    return md_path.stem


def _extract_tags(contents: str) -> list[str]:
    """Extract tags from Obsidian-style YAML frontmatter.

    Looks for a leading '--- ... ---' block and parses it as YAML.
    If a 'tags' field is present, returns it as a list of strings.
    """
    # Quick check for frontmatter at the very top
    if not contents.lstrip().startswith("---"):
        return []

    lines = contents.splitlines()
    if not lines or lines[0].strip() != "---":
        return []

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return []

    frontmatter_text = "\n".join(lines[1:end_idx])

    try:
        data = yaml.safe_load(frontmatter_text) or {}
    except Exception:
        logging.warning("Failed to parse YAML frontmatter for tags")
        return []

    tags = data.get("tags")
    if not tags:
        return []

    # Normalize to list of strings
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, (list, tuple)):
        return [str(t) for t in tags if t is not None]

    return []


def index_obsidian_vault(
    storage: Storage,
    account_name: str,
    vault_path: str | Path,
    *,
    kind: str = "obsidian_note",
    max_files: Optional[int] = None,
) -> list[DocumentRef]:
    """Index all .md files in an Obsidian vault as DocumentRef entries.

    This uses Storage.upsert_document so it works with the current
    JsonFileStorage implementation and future SQL/vector DB backends.

    Args:
        storage: Storage implementation to write documents to.
        account_name: Logical account/owner for these notes.
        vault_path: Root directory of the Obsidian vault.
        kind: Document kind label (defaults to "obsidian_note").
        max_files: Optional cap on number of files to index (for testing).

    Returns:
        A list of DocumentRef objects that were upserted.
    """

    vault = Path(vault_path).expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        raise ValueError(f"Vault path does not exist or is not a directory: {vault}")

    logging.info("Indexing Obsidian vault at %s for account %s", vault, account_name)

    indexed: list[DocumentRef] = []
    count = 0

    for md_file in vault.rglob("*.md"):
        if max_files is not None and count >= max_files:
            break

        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logging.warning("Failed to read %s: %s", md_file, e)
            continue

        doc_id = _stable_doc_id_from_path(md_file)
        title = _extract_title(md_file, text)
        tags = _extract_tags(text)

        metadata = {
            "vault": vault.name,
            "relative_path": str(md_file.relative_to(vault)),
        }

        doc = DocumentRef(
            id=doc_id,
            account_name=account_name,
            path=str(md_file),
            kind=kind,
            title=title,
            tags=tags,
            metadata=metadata,
        )

        try:
            storage.upsert_document(doc)
            indexed.append(doc)
            count += 1
        except Exception as e:
            logging.exception("Failed to upsert document for %s: %s", md_file, e)

    logging.info(
        "Indexed %d Obsidian markdown files from %s for account %s",
        count,
        vault,
        account_name,
    )

    return indexed
