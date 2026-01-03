import os

import pytest

from src.handlers.file_load_handler2 import FileLoadHandler2


class _DummyConfig:
    def get(self, key, default=None):
        # keep it deterministic and writable
        if key == "code_sandbox_path":
            return "/tmp/lucy_test_sandbox"
        return default


def test_file_load_tool_def_uses_relative_path():
    tool = FileLoadHandler2.tool_def()
    props = tool["parameters"]["properties"]
    assert "relative_path" in props
    assert "directory_path" not in props
    assert "file_name" not in props


@pytest.mark.parametrize(
    "rel",
    [
        "",
        ".",
        "..",
        "../x.txt",
        "/abs.txt",
        "C:/abs.txt",
        "C:\\abs.txt",
    ],
)
def test_file_load_rejects_bad_relative_path(rel):
    h = FileLoadHandler2(_DummyConfig())
    res = h.execute({"relative_path": rel})
    assert res["ok"] is False


def test_file_load_reads_file_from_sandbox(tmp_path, monkeypatch):
    # Arrange: create a sandbox and a file inside it
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "hello.txt").write_text("hello", encoding="utf-8")

    # Make get_base_path return our sandbox regardless of account/directory
    monkeypatch.setattr(
        "src.handlers.file_load_handler2.get_base_path",
        lambda config, account_name, directory_path: str(sandbox),
    )

    h = FileLoadHandler2(_DummyConfig())

    # Act
    res = h.execute({"relative_path": "hello.txt"})

    # Assert
    assert res["ok"] is True
    assert res["result"] == "hello"
    assert os.path.realpath(res["resolved_path"]).startswith(os.path.realpath(str(sandbox)))


def test_file_load_rejects_symlink_escape(tmp_path, monkeypatch):
    """If a symlink inside the base points outside, the handler must reject."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    # Create a symlink *file* inside sandbox that points to outside/secret.txt
    link_file = sandbox / "secret_link.txt"
    try:
        link_file.symlink_to(outside / "secret.txt")
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"symlinks not supported/allowed: {e}")

    monkeypatch.setattr(
        "src.handlers.file_load_handler2.get_base_path",
        lambda config, account_name, directory_path: str(sandbox),
    )

    h = FileLoadHandler2(_DummyConfig())
    res = h.execute({"relative_path": "secret_link.txt"})

    assert res["ok"] is False
    # Keep message assertion loose; different OSes may vary
    assert "outside" in res.get("error", "").lower() or "base" in res.get("error", "").lower()
