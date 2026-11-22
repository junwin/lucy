"""Real local-Git integration tests for isolated Marie-Parie editing sessions."""
import subprocess
from pathlib import Path

import pytest

from src.marie_preview import MariePreviewService


class Config:
    def __init__(self, roots, store):
        self.roots, self.store = roots, store

    def get(self, key, default=None):
        return {
            "external_roots": {"repos": str(self.roots)},
            "storage_root_path": str(self.store),
            "storage_namespace": "data",
        }.get(key, default)


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def project(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repos = tmp_path / "repos"
    repos.mkdir()
    working = repos / "marie-parie-web"
    subprocess.run(["git", "clone", str(remote), str(working)], check=True, capture_output=True)
    git(working, "config", "user.name", "Preview Test")
    git(working, "config", "user.email", "preview@example.test")
    git(working, "checkout", "-b", "staging")
    folder = working / "assets" / "New Arrivals"
    folder.mkdir(parents=True)
    (folder / "one.jpg").write_bytes(b"photo-one")
    (folder / "two.jpg").write_bytes(b"photo-two")
    (folder / "gallery.txt").write_text("one.jpg\ntwo.jpg\n")
    (working / "index.html").write_text("<h1>Marie-Parie</h1>")
    (working / "gallery-editor.html").write_text("<html><body>Editor</body></html>")
    git(working, "add", ".")
    git(working, "commit", "-m", "initial")
    git(working, "push", "-u", "origin", "staging")
    return MariePreviewService(Config(repos, tmp_path / "storage")), remote


def test_create_edit_cancel_does_not_change_staging(project):
    service, remote = project
    created = service.create("arla")
    assert created["branch"].startswith("preview/marie-parie/arla-")
    assert created["status"] == "active"
    assert service.status(created["id"], "arla")["changes"] == ""
    with pytest.raises(ValueError):
        service.status(created["id"], "heidi")
    initial = service.gallery(created["id"], "arla", "New Arrivals")
    assert initial["images"] == ["one.jpg", "two.jpg"]
    result = service.save_gallery(created["id"], "arla", "New Arrivals",
                                  ["two.jpg"], initial["sha256"])
    assert result["count"] == 1
    with pytest.raises(ValueError, match="changed"):
        service.save_gallery(created["id"], "arla", "New Arrivals",
                             ["one.jpg"], initial["sha256"])
    with pytest.raises(ValueError):
        service.save_gallery(created["id"], "arla", "New Arrivals", ["../index.html"])
    with pytest.raises(ValueError):
        service.save_gallery(created["id"], "arla", "New Arrivals", ["missing.jpg"])
    assert "gallery.txt" in service.status(created["id"], "arla")["changes"]
    service.cancel(created["id"], "arla")
    assert service.status(created["id"], "arla")["status"] == "cancelled"
    with pytest.raises(ValueError):
        service.from_token(created["view_path"].split("/")[2])
    assert git(remote, "show", "staging:assets/New Arrivals/gallery.txt") == "one.jpg\ntwo.jpg"


def test_publish_fast_forward_and_revoke_preview_tokens(project):
    service, remote = project
    session = service.create("arla")
    first = service.gallery(session["id"], "arla", "New Arrivals")
    service.save_gallery(session["id"], "arla", "New Arrivals", ["two.jpg"], first["sha256"])
    token = session["editor_path"].split("/")[2]
    assert service.from_token(token, editing=True)["id"] == session["id"]
    result = service.publish(session["id"], "arla")
    assert result["status"] == "published"
    assert git(remote, "show", "staging:assets/New Arrivals/gallery.txt") == "two.jpg"
    with pytest.raises(ValueError):
        service.from_token(token, editing=True)
    with pytest.raises(ValueError):
        service.cancel(session["id"], "arla")


def test_readonly_preview_token_cannot_edit(project):
    service, _ = project
    session = service.create("arla")
    reader = session["view_path"].split("/")[2]
    assert service.from_token(reader)["id"] == session["id"]
    with pytest.raises(ValueError):
        service.from_token(reader, editing=True)


def test_unknown_collection_and_duplicate_names_rejected(project):
    service, _ = project
    session = service.create("arla")
    with pytest.raises(ValueError):
        service.gallery(session["id"], "arla", "../New Arrivals")
    with pytest.raises(ValueError):
        service.save_gallery(session["id"], "arla", "New Arrivals", ["one.jpg", "ONE.JPG"])
    service.cancel(session["id"], "arla")


def test_share_preview_branch_without_publishing_to_staging(project):
    service, remote = project
    session = service.create("arla")
    gallery = service.gallery(session["id"], "arla", "New Arrivals")
    service.save_gallery(session["id"], "arla", "New Arrivals", ["two.jpg"], gallery["sha256"])
    result = service.share(session["id"], "arla")
    assert result["shared"] is True
    assert git(remote, "show", f"{result['branch']}:assets/New Arrivals/gallery.txt") == "two.jpg"
    assert git(remote, "show", "staging:assets/New Arrivals/gallery.txt") == "one.jpg\ntwo.jpg"
    published = service.publish(session["id"], "arla")
    assert published["status"] == "published"
    assert git(remote, "show", "staging:assets/New Arrivals/gallery.txt") == "two.jpg"
