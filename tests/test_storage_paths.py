from pathlib import Path
import pytest

from src.storage_paths.storage_paths import StoragePaths


def test_properties_and_resolve_relative_normal(tmp_path):
    root = tmp_path / "storage_root"
    root.mkdir()
    namespace = "mynamespace"

    sp = StoragePaths(str(root), namespace)

    # base should be root/namespace (resolved)
    expected_base = (root / namespace).resolve()
    assert sp.base == expected_base

    # properties
    assert sp.contexts == expected_base / "contexts"
    assert sp.chats == expected_base / "chats"
    assert sp.documents == expected_base / "documents"
    assert sp.users == expected_base / "users"
    assert sp.indexes == expected_base / "indexes"
    assert sp.agents == expected_base / "agents"

    # create a nested file and resolve it
    doc_dir = expected_base / "documents"
    doc_dir.mkdir(parents=True)
    file_path = doc_dir / "file.txt"
    file_path.write_text("hello")

    resolved = sp.resolve_relative("documents/file.txt")
    assert resolved == file_path.resolve()
    assert resolved.read_text() == "hello"


@pytest.mark.parametrize("namespace", ["/tmp/abs", "../../outside"])
def test_constructor_rejects_namespaces_that_escape_root(tmp_path, namespace):
    root = tmp_path / "root"
    root.mkdir()

    # Namespaces that resolve outside the root should raise ValueError
    with pytest.raises(ValueError):
        StoragePaths(str(root), namespace)


def test_resolve_relative_rejects_absolute_and_parent_paths(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    sp = StoragePaths(str(root), "ns")

    # absolute path input should be rejected
    with pytest.raises(ValueError):
        sp.resolve_relative("/etc/passwd")

    # parent traversal should be rejected
    with pytest.raises(ValueError):
        sp.resolve_relative("../outside")


def test_resolve_relative_rejects_symlink_escape(tmp_path):
    root = tmp_path / "root2"
    root.mkdir()
    ns = "ns2"
    base = (root / ns)
    base.mkdir(parents=True)

    # create an outside target with a secret file
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("top secret")

    # inside the namespace create a symlink that points to the outside dir
    link = base / "link"
    link.symlink_to(outside)

    sp = StoragePaths(str(root), ns)

    # accessing through the symlink should be rejected as it escapes the namespace
    with pytest.raises(ValueError):
        sp.resolve_relative("link/secret.txt")
