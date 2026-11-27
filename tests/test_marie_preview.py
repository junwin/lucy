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
            "external_roots": {"repos": str(self.roots), "pictures": str(self.store.parent / "Pictures")},
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


def test_browser_preview_and_gallery_save_capabilities(project):
    from flask import Flask
    from src.marie_preview_web import preview_blueprint
    service, _ = project
    session = service.create("arla")
    view_token = session["view_path"].split("/")[2]
    edit_token = session["editor_path"].split("/")[2]
    app = Flask(__name__)
    app.config["lucy_config"] = Config(service.repo.parent, service.base.parent.parent)
    app.register_blueprint(preview_blueprint)
    client = app.test_client()
    assert client.get(f"/preview/{view_token}/").status_code == 200
    html = client.get(f"/preview/{edit_token}/gallery-editor.html")
    assert html.status_code == 200
    assert b"Save to Lucy preview" in html.data
    endpoint = f"/preview/{view_token}/api/gallery/New%20Arrivals"
    assert client.put(endpoint, json={"images": ["two.jpg"]}).status_code == 403
    editor = f"/preview/{edit_token}/api/gallery/New%20Arrivals"
    old = client.get(editor)
    assert old.status_code == 200
    assert old.json["images"] == ["one.jpg", "two.jpg"]
    saved = client.put(editor, json={"images": ["two.jpg"],
                                     "expected_sha": old.json["sha256"]})
    assert saved.status_code == 200
    assert client.get(editor).json["images"] == ["two.jpg"]
    assert client.get(f"/preview/{edit_token}/.git/config").status_code == 404
    service.cancel(session["id"], "arla")
    assert client.get(f"/preview/{view_token}/").status_code == 404

def test_preview_urls_default_to_local_lucy_origin(project):
    service, _ = project
    session = service.create("arla")
    assert session["view_url"] == "http://localhost:5000" + session["view_path"]
    assert session["editor_url"] == "http://localhost:5000" + session["editor_path"]
    recovered = service.status(session["id"], "arla")
    assert recovered["view_url"] == session["view_url"]
    service.cancel(session["id"], "arla")


def test_preview_url_can_use_configured_ngrok_origin(project):
    service, _ = project
    original = service.preview_origin
    service.preview_origin = "https://example.ngrok.app"
    session = service.create("arla")
    assert session["view_url"].startswith("https://example.ngrok.app/preview/")
    service.cancel(session["id"], "arla")
    service.preview_origin = original


def test_import_new_batch_replaces_old_same_filename_image_bytes(project):
    service, remote = project
    session = service.create("arla")
    folder = Path(session["worktree"]) / "assets" / "New Arrivals"
    original_bytes = (folder / "one.jpg").read_bytes()
    pictures = service.config.get("external_roots")["pictures"]
    batch = "batch-0123456789ab"
    source = Path(pictures) / "marie-parie" / "prepared" / "web" / batch
    source.mkdir(parents=True)
    (source / "one.jpg").write_bytes(b"arla-new-photo-not-john-old-photo")
    (source / "three.jpg").write_bytes(b"new-third-photo")
    old_gallery = service.gallery(session["id"], "arla", "New Arrivals")
    result = service.import_web_batch(session["id"], "arla", "New Arrivals",
                                      batch, replace=True,
                                      expected_sha=old_gallery["sha256"])
    assert result["count"] == 2
    assert result["gallery_count"] == 2
    assert result["replace"] is True
    assert result["imported"][0].startswith("one-")
    assert result["imported"][0].endswith(".jpg")
    assert (folder / "one.jpg").read_bytes() == original_bytes
    assert (folder / result["imported"][0]).read_bytes() == b"arla-new-photo-not-john-old-photo"
    assert service.gallery(session["id"], "arla", "New Arrivals")["images"] == result["imported"]
    assert (source / "one.jpg").read_bytes() == b"arla-new-photo-not-john-old-photo"
    # Repeating import is idempotent and keeps the same image bytes and names.
    again = service.import_web_batch(session["id"], "arla", "New Arrivals",
                                     batch, replace=True, expected_sha=result["sha256"])
    assert again["imported"] == result["imported"]
    assert again["sha256"] == result["sha256"]
    # Only preview files changed, remote staging remains unmodified.
    assert git(remote, "show", "staging:assets/New Arrivals/gallery.txt") == "one.jpg\\ntwo.jpg"


def test_import_batch_rejects_missing_or_stale_batch_without_gallery_changes(project):
    service, _ = project
    session = service.create("arla")
    before = service.gallery(session["id"], "arla", "New Arrivals")
    with pytest.raises(ValueError, match="Prepared web batch not found"):
        service.import_web_batch(session["id"], "arla", "New Arrivals",
                                 "batch-aaaaaaaaaaaa", replace=True)
    source = Path(service.config.get("external_roots")["pictures"]) / "marie-parie" / "prepared" / "web" / "batch-aaaaaaaaaaaa"
    source.mkdir(parents=True)
    (source / "new.jpg").write_bytes(b"new")
    with pytest.raises(ValueError, match="changed since"):
        service.import_web_batch(session["id"], "arla", "New Arrivals",
                                 "batch-aaaaaaaaaaaa", replace=True,
                                 expected_sha="stale")
    assert service.gallery(session["id"], "arla", "New Arrivals") == before
