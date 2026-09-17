import json
import os
import shutil

import pytest

from src.handlers.patch_apply_handler import PatchApplyHandler


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


class DummyConfig:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, key, default=None):
        return self._mapping.get(key, default)


def _handler_for(base, root_name="tmp"):
    config = DummyConfig({"external_roots": {root_name: str(base)}})
    return PatchApplyHandler(config=config)


def _replace_patch(path, old="old", new="new"):
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{old}\n"
        f"+{new}\n"
    )


def _args(path, patch_content, **overrides):
    values = {
        "location": "external",
        "external_root": "tmp",
        "path": path,
        "patch_content": patch_content,
        "check_only": False,
    }
    values.update(overrides)
    return values


def test_patch_apply_applies_exact_requested_path(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("old\n", encoding="utf-8")
    handler = _handler_for(tmp_path)

    result = handler.execute(_args("hello.txt", _replace_patch("hello.txt")))

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["path"] == "hello.txt"
    assert result["affected_paths"] == ["hello.txt"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_patch_apply_check_only_does_not_modify_file(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("old\n", encoding="utf-8")
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args(
            "hello.txt",
            _replace_patch("hello.txt"),
            check_only=True,
        )
    )

    assert result["ok"] is True
    assert result["applied"] is False
    assert result["affected_paths"] == ["hello.txt"]
    assert target.read_text(encoding="utf-8") == "old\n"


def test_invalid_patch_fails_without_modifying_file(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("old\n", encoding="utf-8")
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args("hello.txt", _replace_patch("hello.txt", old="not-present"))
    )

    assert result["ok"] is False
    assert result["applied"] is False
    assert "check failed" in result["error"]
    assert target.read_text(encoding="utf-8") == "old\n"


@pytest.mark.parametrize(
    "path",
    [
        "../hello.txt",
        "/tmp/hello.txt",
        "nested/../../hello.txt",
        r"C:\\temp\\hello.txt",
        r"nested\\hello.txt",
    ],
)
def test_unsafe_paths_are_rejected(tmp_path, path):
    handler = _handler_for(tmp_path)

    result = handler.execute(_args(path, _replace_patch("hello.txt")))

    assert result["ok"] is False
    assert result["applied"] is False


def test_external_location_requires_named_root(tmp_path):
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args(
            "hello.txt",
            _replace_patch("hello.txt"),
            external_root="",
        )
    )

    assert result["ok"] is False
    assert result["error"] == "external_root is required for location='external'"


def test_storage_location_rejects_external_root(tmp_path):
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args(
            "hello.txt",
            _replace_patch("hello.txt"),
            location="storage",
        )
    )

    assert result["ok"] is False
    assert result["error"] == "external_root must be empty for location='storage'"


def test_unknown_external_root_is_rejected(tmp_path):
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args(
            "hello.txt",
            _replace_patch("hello.txt"),
            external_root="unknown",
        )
    )

    assert result["ok"] is False
    assert "Unknown external_root" in result["error"]


def test_patch_targeting_a_different_file_is_rejected(tmp_path):
    requested = tmp_path / "requested.txt"
    other = tmp_path / "other.txt"
    requested.write_text("old\n", encoding="utf-8")
    other.write_text("old\n", encoding="utf-8")
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args("requested.txt", _replace_patch("other.txt"))
    )

    assert result["ok"] is False
    assert result["error"] == "patch must affect exactly the requested path"
    assert result["affected_paths"] == ["other.txt"]
    assert requested.read_text(encoding="utf-8") == "old\n"
    assert other.read_text(encoding="utf-8") == "old\n"


def test_multi_file_patch_is_rejected_atomically(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("old\n", encoding="utf-8")
    second.write_text("old\n", encoding="utf-8")
    handler = _handler_for(tmp_path)
    patch = _replace_patch("first.txt") + _replace_patch("second.txt")

    result = handler.execute(_args("first.txt", patch))

    assert result["ok"] is False
    assert result["affected_paths"] == ["first.txt", "second.txt"]
    assert first.read_text(encoding="utf-8") == "old\n"
    assert second.read_text(encoding="utf-8") == "old\n"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks are unavailable")
def test_symlink_escape_is_rejected(tmp_path):
    base = tmp_path / "base"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (outside / "hello.txt").write_text("old\n", encoding="utf-8")
    os.symlink(outside, base / "escape")
    handler = _handler_for(base)

    result = handler.execute(
        _args(
            "escape/hello.txt",
            _replace_patch("escape/hello.txt"),
        )
    )

    assert result["ok"] is False
    assert result["error"] == "path escapes the configured root"
    assert (outside / "hello.txt").read_text(encoding="utf-8") == "old\n"


def test_invalid_json_returns_explicit_error(tmp_path):
    handler = _handler_for(tmp_path)

    result = json.loads(handler.execute_raw("{not-json"))

    assert result["ok"] is False
    assert result["applied"] is False
    assert result["error"] == "arguments_raw is not valid JSON"


def test_binary_patch_is_rejected(tmp_path):
    handler = _handler_for(tmp_path)

    result = handler.execute(
        _args("hello.bin", "GIT binary patch\nliteral 0\n")
    )

    assert result["ok"] is False
    assert "binary patches" in result["error"]


def test_strict_schema_requires_every_property():
    parameters = PatchApplyHandler.tool_def()["parameters"]

    assert set(parameters["required"]) == set(parameters["properties"])
    assert parameters["additionalProperties"] is False
