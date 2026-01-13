import os
import pytest
from pathlib import Path

from src.handlers.handler_utils import get_base_path


class DummyConfig:
    def __init__(self, **kwargs):
        self._d = dict(kwargs)

    def get(self, key: str, default=None):
        return self._d.get(key, default)


def test_get_base_path_prefers_lucy_user_root(tmp_path, monkeypatch):
    # LUCY_USER_ROOT should take precedence
    lucy_root = tmp_path / "lucyroot"
    (lucy_root / "junwin").mkdir(parents=True)

    monkeypatch.setenv("LUCY_USER_ROOT", str(lucy_root))
    monkeypatch.delenv("HOME", raising=False)

    cfg = DummyConfig()
    p = get_base_path(cfg, "junwin", "~")
    assert os.path.realpath(p) == os.path.realpath(str(lucy_root / "junwin"))


def test_get_base_path_uses_home_for_matching_username(tmp_path, monkeypatch):
    # If $HOME basename matches the account, use HOME directly
    home = tmp_path / "home" / "junwin"
    home.mkdir(parents=True)

    monkeypatch.delenv("LUCY_USER_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(home))

    cfg = DummyConfig()
    p = get_base_path(cfg, "junwin", "~")
    assert os.path.realpath(p) == os.path.realpath(str(home))


def test_get_base_path_falls_back_to_home_account_dir(tmp_path, monkeypatch):
    # If HOME/<account> exists, use that for other usernames
    home = tmp_path / "home" / "junwin"
    home.mkdir(parents=True)
    fpe_dir = tmp_path / "home" / "fpe"
    fpe_dir.mkdir(parents=True)

    # point HOME to tmp/home/junwin
    monkeypatch.delenv("LUCY_USER_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(home))

    # monkeypatch /home/fpe existence by intercepting isdir and realpath
    realpath_orig = os.path.realpath
    isdir_orig = os.path.isdir

    def fake_realpath(p):
        if os.path.normpath(p) == os.path.normpath(os.path.join(os.path.sep, "home", "fpe")):
            return str(fpe_dir)
        return realpath_orig(p)

    def fake_isdir(p):
        if os.path.normpath(p) == os.path.normpath(os.path.join(os.path.sep, "home", "fpe")):
            return True
        return isdir_orig(p)

    monkeypatch.setattr(os.path, "realpath", fake_realpath)
    monkeypatch.setattr(os.path, "isdir", fake_isdir)

    cfg = DummyConfig()
    p = get_base_path(cfg, "fpe", "~")
    assert os.path.realpath(p) == os.path.realpath(str(fpe_dir))

    # restore monkeypatch will be handled by fixture teardown
