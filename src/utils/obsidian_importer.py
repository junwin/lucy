from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

import yaml  # type: ignore

from src.storage.base import Storage
from src.storage.models import DocumentRef


def _stable_doc_id_from_path(vault_name: str, relative_path: str) -> str:
    """Create a stable, portable document ID from vault name and relative path.

    Uses SHA-256 of ``vault_name + relative_path`` so the same vault produces
    identical IDs regardless of which machine it sits on.

    Args:
        vault_name: Name of the vault root directory (e.g. ``"myvault"``).
        relative_path: Path of the markdown file relative to the vault root
            (e.g. ``"folder/note.md"``).

    Returns:
        A hex-encoded SHA-256 digest.
    """
    raw = f"{vault_name}/{relative_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def index_obsidian_file(
    storage: Storage,
    account_name: str,
    md_path: str | Path,
    *,
    vault_root: Optional[str | Path] = None,
    kind: str = "obsidian_note",
) -> list[DocumentRef]:
    """Index a single Obsidian markdown file as a DocumentRef entry.

    Parses and tags the file using the same logic as the vault-based indexer.
    When *vault_root* is provided, the relative path and vault name are derived
    from it (the file must be inside the vault root).  When *vault_root* is
    *None*, the parent directory name is used as the vault name and only the
    filename is used as the relative path.

    Args:
        storage: Storage implementation to write the document to.
        account_name: Logical account/owner for the note.
        md_path: Path to a single ``.md`` file.
        vault_root: Optional root directory of the Obsidian vault that the file
            belongs to.  If given, the relative path inside the vault and the
            vault name are derived from this directory.
        kind: Document kind label (defaults to ``"obsidian_note"``).

    Returns:
        A list containing the single ``DocumentRef`` that was upserted, or an
        empty list if the file could not be read or upserted.

    Raises:
        ValueError: If *md_path* does not exist, is not a file, or does not
            have a ``.md`` extension.
        ValueError: If *vault_root* is provided but *md_path* does not lie
            under it.
    """
    md = Path(md_path).expanduser().resolve()

    if not md.exists():
        raise ValueError(f"File does not exist: {md}")
    if not md.is_file():
        raise ValueError(f"Path is not a file: {md}")
    if md.suffix.lower() != ".md":
        raise ValueError(f"File must have a .md extension: {md}")

    # Determine vault name and relative path
    if vault_root is not None:
        vault = Path(vault_root).expanduser().resolve()
        if not vault.exists():
            raise ValueError(f"Vault root does not exist: {vault}")
        if not vault.is_dir():
            raise ValueError(f"Vault root is not a directory: {vault}")
        try:
            relative_path = str(md.relative_to(vault))
        except ValueError:
            raise ValueError(
                f"File {md} is not inside vault root {vault}"
            )
        vault_name = vault.name
    else:
        vault_name = md.parent.name
        relative_path = md.name

    # Read file contents
    try:
        text = md.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logging.warning("Failed to read %s: %s", md, e)
        return []

    # Reuse existing parsing helpers
    doc_id = _stable_doc_id_from_path(vault_name, relative_path)
    title = _extract_title(md, text)
    tags = _extract_tags(text)

    metadata = {
        "vault": vault_name,
        "relative_path": relative_path,
    }

    doc = DocumentRef(
        id=doc_id,
        account_name=account_name,
        path=str(md),
        kind=kind,
        title=title,
        tags=tags,
        metadata=metadata,
    )

    try:
        storage.upsert_document(doc)
        logging.info(
            "Indexed single file %s as doc %s for account %s",
            md, doc_id, account_name,
        )
        return [doc]
    except Exception as e:
        logging.exception("Failed to upsert document for %s: %s", md, e)
        return []


def index_obsidian_vault(
    storage: Storage,
    account_name: str,
    vault_path: str | Path,
    *,
    kind: str = "obsidian_note",
    max_files: Optional[int] = None,
    no_recursion: bool = False,
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
        no_recursion: If True, only index .md files directly inside
            vault_path, skipping all subdirectories.

    Returns:
        A list of DocumentRef objects that were upserted.
    """

    vault = Path(vault_path).expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        raise ValueError(f"Vault path does not exist or is not a directory: {vault}")

    logging.info("Indexing Obsidian vault at %s for account %s", vault, account_name)

    indexed: list[DocumentRef] = []
    count = 0

    vault_name = vault.name

    # When no_recursion is set, only scan the top-level directory.
    glob_pattern = vault.glob("*.md") if no_recursion else vault.rglob("*.md")

    for md_file in glob_pattern:
        if max_files is not None and count >= max_files:
            break

        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logging.warning("Failed to read %s: %s", md_file, e)
            continue

        relative_path = str(md_file.relative_to(vault))
        doc_id = _stable_doc_id_from_path(vault_name, relative_path)
        title = _extract_title(md_file, text)
        tags = _extract_tags(text)

        metadata = {
            "vault": vault_name,
            "relative_path": relative_path,
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
