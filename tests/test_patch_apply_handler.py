import os
import tempfile
import importlib.util
from pathlib import Path


def _load_patch_handler_class():
    path = Path(__file__).resolve().parents[1] / "src" / "handlers" / "patch_apply_handler.py"
    spec = importlib.util.spec_from_file_location("patch_apply_handler", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PatchApplyHandler


class DummyConfig:
    def __init__(self, mapping):
        self._m = mapping

    def get(self, key, default=None):
        return self._m.get(key, default)


def test_patch_apply_applies_patch(tmp_path):
    PatchApplyHandler = _load_patch_handler_class()

    # Prepare a temporary directory with a file to patch
    base = tmp_path / "repo"
    base.mkdir()
    f = base / "hello.txt"
    f.write_text("old\n")

    # Build a simple unified diff patch
    patch = (
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    config = DummyConfig({"external_roots": {"tmp": str(base)}})
    handler = PatchApplyHandler(config=config)

    args = {
        "location": "external",
        "external_root": "tmp",
        "path": "hello.txt",
        "patch_content": patch,
    }

    result = handler.execute(args)
    assert result["ok"] is True
    assert result["applied"] is True
    # verify file content changed
    assert f.read_text() == "new\n"


def test_patch_apply_check_only_does_not_apply(tmp_path):
    PatchApplyHandler = _load_patch_handler_class()

    base = tmp_path / "repo2"
    base.mkdir()
    f = base / "hello2.txt"
    f.write_text("old\n")

    patch = (
        "--- a/hello2.txt\n"
        "+++ b/hello2.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    config = DummyConfig({"external_roots": {"tmp2": str(base)}})
    handler = PatchApplyHandler(config=config)

    args = {
        "location": "external",
        "external_root": "tmp2",
        "path": "hello2.txt",
        "patch_content": patch,
        "check_only": True,
    }

    result = handler.execute(args)
    assert result["ok"] is True
    assert result["applied"] is False
    assert f.read_text() == "old\n"
