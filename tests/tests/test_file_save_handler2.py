import os

import pytest

from src.handlers.file_save_handler import FileSaveHandler2


class _DummyConfig:
    def get(self, key, default=None):
        # keep it deterministic and writable
        if key == "code_sandbox_path":
            return "/tmp/lucy_test_sandbox"
        return default


def test_file_save_tool_def_uses_relative_path():
    tool = FileSaveHandler2.tool_def()
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
def test_file_save_rejects_bad_relative_path(rel):
    h = FileSaveHandler2(_DummyConfig())
    res = h.execute({"relative_path": rel, "file_content": "x", "overwrite": True})
    assert res["ok"] is False


def test_file_save_rejects_non_string_content():
    h = FileSaveHandler2(_DummyConfig())
    res = h.execute({"relative_path": "a.txt", "file_content": {"x": 1}, "overwrite": True})
    assert res["ok"] is False
    assert "file_content must be a string" in res["error"]


def test_file_save_writes_file_to_sandbox(tmp_path, monkeypatch):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    monkeypatch.setattr(
        "src.handlers.file_save_handler.get_base_path",
        lambda config, account_name, directory_path: str(sandbox),
    )

    h = FileSaveHandler2(_DummyConfig())
    res = h.execute({"relative_path": "dir1/hello.txt", "file_content": "hello", "overwrite": True})

    assert res["ok"] is True
    assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "hello"
    assert os.path.realpath(res["resolved_path"]).startswith(os.path.realpath(str(sandbox)))


def test_file_save_symlink_escape_current_behavior_note(tmp_path, monkeypatch):
    """NOTE: Current FileSaveHandler2 behavior allows writing through a symlinked directory.

    The handler's containment check is performed on the *directory base* returned by get_base_path
    and the *file name* only. Because the file name is joined directly to base_path, a symlink
    directory in the *relative_path* is not part of the final joined path, so it cannot be used
    to escape.

    If the implementation changes to join the full normalized relative_path to base_path,
    this test should be updated to assert rejection.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()

    link_dir = sandbox / "link"
    try:
        link_dir.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"symlinks not supported/allowed: {e}")

    monkeypatch.setattr(
        "src.handlers.file_save_handler.get_base_path",
        lambda config, account_name, directory_path: str(sandbox),
    )

    h = FileSaveHandler2(_DummyConfig())
    res = h.execute({"relative_path": "link/secret.txt", "file_content": "secret", "overwrite": True})

    # With current behavior, this writes to sandbox/secret.txt (not outside).
    assert res["ok"] is True
    assert (sandbox / "secret.txt").read_text(encoding="utf-8") == "secret"
