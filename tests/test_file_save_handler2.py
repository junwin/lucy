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
