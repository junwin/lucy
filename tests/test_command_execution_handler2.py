import pytest

from src.handlers.command_execution_handler2 import CommandExecutionHandler2


class DummyConfig:
    def __init__(self, **kwargs):
        self._d = dict(kwargs)

    def get(self, key: str, default=None):
        return self._d.get(key, default)


def _mk_handler(tmp_path):
    # minimal config; we only test path validation helper here
    return CommandExecutionHandler2(DummyConfig(code_sandbox_path=str(tmp_path)))


def test_validate_and_normalize_relative_path_allows_dot(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path(".")

    assert err == ""
    assert norm == "."


def test_validate_and_normalize_relative_path_empty_normalizes_to_dot(tmp_path):
    """os.path.normpath('') becomes '.', so the helper treats it as base dir."""
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("")

    assert err == ""
    assert norm == "."


def test_validate_and_normalize_relative_path_blocks_parent(tmp_path):
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("..")

    assert norm == ""
    assert "parent" in err or ".." in err


def test_validate_and_normalize_relative_path_allows_internal_dotdot_normalization(tmp_path):
    """Current behavior: 'a/../b' normalizes to 'b' and is allowed."""
    h = _mk_handler(tmp_path)

    norm, err = h._validate_and_normalize_relative_path("a/../b")

    assert err == ""
    assert norm == "b"
