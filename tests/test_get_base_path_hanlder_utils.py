import os
import pytest


from src.handlers.handler_utils import get_base_path


class DummyConfig:
    def __init__(self, **kwargs):
        self._d = dict(kwargs)

    def get(self, key: str, default=None):
        return self._d.get(key, default)


def _mk_config(tmp_path):
    # sandbox root
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    return DummyConfig(code_sandbox_path=str(sandbox)), sandbox


def test_get_base_path_basic_join(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    p = get_base_path(config, "junwin", "projectA")
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin", "projectA"))

    assert os.path.realpath(p) == expected


def test_get_base_path_strips_whitespace(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    p = get_base_path(config, "junwin", "  projectA  ")
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin", "projectA"))

    assert os.path.realpath(p) == expected


def test_get_base_path_normalizes_slashes(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    # mixed slashes should still resolve to the same place
    p = get_base_path(config, "junwin", r"dir1\dir2/subdir")
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin", "dir1", "dir2", "subdir"))

    assert os.path.realpath(p) == expected


def test_get_base_path_resolves_dotdot_inside_sandbox(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    p = get_base_path(config, "junwin", "dir1/dir2/../dir3")
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin", "dir1", "dir3"))

    assert os.path.realpath(p) == expected


def test_get_base_path_blocks_traversal_outside_sandbox(tmp_path):
    config, _ = _mk_config(tmp_path)

    with pytest.raises(ValueError, match="traversal|outside|allowed"):
        get_base_path(config, "junwin", "../../etc")


def test_get_base_path_tilde_means_account_root(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    p1 = get_base_path(config, "junwin", "~")
    p2 = get_base_path(config, "junwin", "~/")
    p3 = get_base_path(config, "junwin", "~\\")   # <-- fixed
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin"))

    assert os.path.realpath(p1) == expected
    assert os.path.realpath(p2) == expected
    assert os.path.realpath(p3) == expected


def test_get_base_path_tilde_subdir(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    p = get_base_path(config, "junwin", "~/work")
    expected = os.path.realpath(os.path.join(str(sandbox), "junwin", "work"))

    assert os.path.realpath(p) == expected


def test_get_base_path_allows_absolute_only_if_within_account_root(tmp_path):
    config, sandbox = _mk_config(tmp_path)

    # create an absolute path under sandbox/junwin
    inside = os.path.realpath(os.path.join(str(sandbox), "junwin", "inner"))
    os.makedirs(inside, exist_ok=True)

    p = get_base_path(config, "junwin", inside)
    assert os.path.realpath(p) == inside


def test_get_base_path_blocks_absolute_outside_account_root(tmp_path):
    config, _ = _mk_config(tmp_path)

    # pick something that is definitely outside the tmp sandbox
    outside = os.path.realpath(os.path.join(os.path.sep, "tmp")) if os.name != "nt" else os.path.realpath(r"C:\Windows")

    with pytest.raises(ValueError, match="relative|sandbox|outside|allowed"):
        get_base_path(config, "junwin", outside)
