"""Tests for the Obsidian importer module.

Focus: document ID portability across machines and single-file import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.utils.obsidian_importer import (
    _stable_doc_id_from_path,
    index_obsidian_file,
    index_obsidian_vault,
)

# ---------------------------------------------------------------------------
# In-memory document storage for testing (implements only document methods)
# ---------------------------------------------------------------------------


class _DictDocStorage:
    """Minimal in-memory Storage duck-type that implements document methods."""

    def __init__(self) -> None:
        self._docs: Dict[str, Any] = {}

    def upsert_document(self, doc: Any) -> None:
        self._docs[doc.id] = doc

    def get_document(self, document_id: str) -> Optional[Any]:
        return self._docs.get(document_id)

    def list_documents(
        self,
        account_name: str,
        kind: Optional[str] = None,
        tag: Optional[str] = None,
        select_limit: int = 100,
    ) -> List[Any]:
        results = [d for d in self._docs.values() if d.account_name == account_name]
        if kind:
            results = [d for d in results if d.kind == kind]
        if tag:
            results = [d for d in results if tag in d.tags]
        return results[:select_limit]


# ---------------------------------------------------------------------------
# Existing tests for _stable_doc_id_from_path
# ---------------------------------------------------------------------------


class TestStableDocIdFromPath:
    """Portable document ID strategy: sha256(vault_name + relative_path)."""

    def test_same_vault_same_path_always_same_id(self):
        """Same vault name + same relative path → identical ID every time."""
        id1 = _stable_doc_id_from_path("myvault", "folder/note.md")
        id2 = _stable_doc_id_from_path("myvault", "folder/note.md")
        assert id1 == id2
        assert isinstance(id1, str)
        assert len(id1) == 64  # SHA-256 hex digest

    def test_different_vaults_different_ids(self):
        """Same relative path under different vaults → different IDs."""
        id_a = _stable_doc_id_from_path("vault_a", "note.md")
        id_b = _stable_doc_id_from_path("vault_b", "note.md")
        assert id_a != id_b

    def test_different_paths_different_ids(self):
        """Same vault, different relative paths → different IDs."""
        id1 = _stable_doc_id_from_path("myvault", "a.md")
        id2 = _stable_doc_id_from_path("myvault", "b.md")
        assert id1 != id2

    def test_id_independent_of_absolute_path(self):
        """ID does NOT depend on absolute filesystem location.

        Cross-machine scenario:
          Machine A: /home/user/obsidian/myvault/folder/note.md
          Machine B: /Users/john/Notes/myvault/folder/note.md
        Both should produce the same ID because only vault_name + relative_path
        are used.
        """
        id_machine_a = _stable_doc_id_from_path("myvault", "folder/note.md")
        id_machine_b = _stable_doc_id_from_path("myvault", "folder/note.md")
        assert id_machine_a == id_machine_b

    def test_subdirectory_paths(self):
        """Nested relative paths work correctly."""
        id1 = _stable_doc_id_from_path("vault", "sub/deep/note.md")
        id2 = _stable_doc_id_from_path("vault", "sub/deep/note.md")
        assert id1 == id2

    def test_vault_name_with_spaces(self):
        """Vault names containing spaces or special chars still produce stable IDs."""
        id1 = _stable_doc_id_from_path("My Obsidian Vault", "my note.md")
        id2 = _stable_doc_id_from_path("My Obsidian Vault", "my note.md")
        assert id1 == id2

    def test_different_vault_same_path_produces_different_ids(self):
        """Regression: same relative path under differently-named vaults differs."""
        id_v1 = _stable_doc_id_from_path("vault1", "journal/2024-01-01.md")
        id_v2 = _stable_doc_id_from_path("vault2", "journal/2024-01-01.md")
        assert id_v1 != id_v2

    def test_id_format_is_hex(self):
        """ID is a 64-character hex string (SHA-256)."""
        doc_id = _stable_doc_id_from_path("testvault", "test.md")
        assert len(doc_id) == 64
        # All chars should be valid hex
        int(doc_id, 16)


# ---------------------------------------------------------------------------
# Tests for index_obsidian_file
# ---------------------------------------------------------------------------


class TestIndexObsidianFile:
    """Single-file import: parsing, tagging, and storage."""

    def test_indexes_simple_file(self, tmp_path: Path) -> None:
        """A basic .md file is parsed, tagged, and stored."""
        storage = _DictDocStorage()
        md = tmp_path / "mynote.md"
        md.write_text("# Hello\n\nSome content.\n")

        docs = index_obsidian_file(
            storage=storage,
            account_name="testuser",
            md_path=md,
        )

        assert len(docs) == 1
        doc = docs[0]
        assert doc.account_name == "testuser"
        assert doc.title == "mynote"
        assert doc.kind == "obsidian_note"
        assert doc.path == str(md.resolve())
        assert doc.tags == []  # no frontmatter
        assert doc.metadata["vault"] == tmp_path.name
        assert doc.metadata["relative_path"] == "mynote.md"

    def test_extracts_frontmatter_tags(self, tmp_path: Path) -> None:
        """Tags in YAML frontmatter are extracted correctly."""
        storage = _DictDocStorage()
        md = tmp_path / "tagged.md"
        md.write_text("---\ntags: [obsidian, test, import]\n---\n\nContent.\n")

        docs = index_obsidian_file(storage=storage, account_name="testuser", md_path=md)
        assert len(docs) == 1
        assert sorted(docs[0].tags) == ["import", "obsidian", "test"]

    def test_id_is_stable(self, tmp_path: Path) -> None:
        """Same vault name + same relative path → identical doc ID."""
        vault = tmp_path / "myvault"
        vault.mkdir()
        md = vault / "note.md"
        md.write_text("same content")

        storage1 = _DictDocStorage()
        docs1 = index_obsidian_file(
            storage=storage1,
            account_name="test",
            md_path=md,
            vault_root=vault,
        )

        storage2 = _DictDocStorage()
        docs2 = index_obsidian_file(
            storage=storage2,
            account_name="test",
            md_path=md,
            vault_root=vault,
        )

        assert docs1[0].id == docs2[0].id

    def test_with_vault_root(self, tmp_path: Path) -> None:
        """When vault_root is provided, relative path and vault name are derived."""
        vault = tmp_path / "myvault"
        sub = vault / "subdir"
        sub.mkdir(parents=True)
        md = sub / "deep.md"
        md.write_text("deep note")

        storage = _DictDocStorage()
        docs = index_obsidian_file(
            storage=storage,
            account_name="tester",
            md_path=md,
            vault_root=vault,
        )

        assert len(docs) == 1
        doc = docs[0]
        assert doc.metadata["vault"] == "myvault"
        assert doc.metadata["relative_path"] == "subdir/deep.md"

    def test_file_outside_vault_root_raises(self, tmp_path: Path) -> None:
        """File that is not under vault_root raises ValueError."""
        vault = tmp_path / "vault"
        vault.mkdir()
        outside = tmp_path / "outside.md"
        outside.write_text("outside")

        with pytest.raises(ValueError, match="not inside vault root"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=outside,
                vault_root=vault,
            )

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Non-existent file path raises ValueError."""
        missing = tmp_path / "nope.md"
        with pytest.raises(ValueError, match="does not exist"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=missing,
            )

    def test_non_md_file_raises(self, tmp_path: Path) -> None:
        """File without .md extension raises ValueError."""
        txt = tmp_path / "notes.txt"
        txt.write_text("text")
        with pytest.raises(ValueError, match=".md extension"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=txt,
            )

    def test_directory_raises(self, tmp_path: Path) -> None:
        """Passing a directory path raises ValueError."""
        with pytest.raises(ValueError, match="not a file"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=tmp_path,
            )

    def test_custom_kind(self, tmp_path: Path) -> None:
        """The kind parameter is forwarded to DocumentRef."""
        storage = _DictDocStorage()
        md = tmp_path / "custom.md"
        md.write_text("custom kind test")

        docs = index_obsidian_file(
            storage=storage,
            account_name="test",
            md_path=md,
            kind="my_custom_kind",
        )

        assert len(docs) == 1
        assert docs[0].kind == "my_custom_kind"

    def test_nonexistent_vault_root_raises(self, tmp_path: Path) -> None:
        """Non-existent vault_root raises ValueError."""
        md = tmp_path / "note.md"
        md.write_text("content")
        fake_vault = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="does not exist"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=md,
                vault_root=fake_vault,
            )

    def test_vault_root_is_file_raises(self, tmp_path: Path) -> None:
        """vault_root that is a file (not dir) raises ValueError."""
        md = tmp_path / "note.md"
        md.write_text("content")
        a_file = tmp_path / "afile.txt"
        a_file.write_text("nope")

        with pytest.raises(ValueError, match="not a directory"):
            index_obsidian_file(
                storage=_DictDocStorage(),
                account_name="test",
                md_path=md,
                vault_root=a_file,
            )

    def test_upsert_failure_returns_empty(self, tmp_path: Path) -> None:
        """If upsert_document raises, the function returns an empty list gracefully."""
        md = tmp_path / "broken.md"
        md.write_text("content")

        class _BrokenStorage(_DictDocStorage):
            def upsert_document(self, doc: Any) -> None:
                raise RuntimeError("storage failure")

        docs = index_obsidian_file(
            storage=_BrokenStorage(),
            account_name="test",
            md_path=md,
        )
        assert docs == []
