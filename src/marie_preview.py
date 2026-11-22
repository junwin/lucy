"""Isolated Marie-Parie preview worktrees: core functions reusable by MCP.

No HTTP or agent dependencies. Only changes under assets/ may be published.
Tokens are capability secrets; do not log them or include them in Git commits.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path

_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
_COLLECTION = re.compile(r"^[^/\\\\.][^/\\\\]*$")
_FILENAME = re.compile(r"^[^/\\\\]+\\.(?:jpg|jpeg|png)$", re.I)


def _git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def _within(root: Path, path: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path escapes the preview worktree")
    return path


class MariePreviewService:
    def __init__(self, config):
        roots = config.get("external_roots") or {}
        if not isinstance(roots, dict) or not roots.get("repos"):
            raise ValueError("external_roots.repos is required")
        self.repo = Path(roots["repos"]).resolve() / "marie-parie-web"
        if not (self.repo / ".git").exists():
            raise ValueError("Marie-Parie web Git checkout not found")
        storage = Path(config.get("storage_root_path", "/home/junwin/lucy_storage"))
        namespace = config.get("storage_namespace", "data")
        self.base = storage / namespace / "marie_parie_previews"
        self.base.mkdir(parents=True, exist_ok=True)

    def _state_path(self, sid):
        if not re.fullmatch(r"[0-9a-f]{32}", str(sid)):
            raise ValueError("Invalid preview session ID")
        return self.base / (sid + ".json")

    def _load(self, sid, owner=None):
        state = json.loads(self._state_path(sid).read_text(encoding="utf-8"))
        if owner is not None and state["owner"] != owner:
            raise ValueError("Preview session not available to this account")
        return state

    def _save(self, state):
        path = self._state_path(state["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    def create(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", owner):
            raise ValueError("Invalid preview owner")
        _git(self.repo, "fetch", "origin", "staging")
        sid = uuid.uuid4().hex
        branch = f"preview/marie-parie/{owner}-{sid[:10]}"
        worktree = self.base / ("worktree-" + sid)
        _git(self.repo, "worktree", "add", "-b", branch, str(worktree), "origin/staging")
        state = {
            "id": sid, "owner": owner, "branch": branch, "status": "active",
            "worktree": str(worktree),
            "base_sha": _git(worktree, "rev-parse", "HEAD"),
            "view_token": secrets.token_urlsafe(32),
            "edit_token": secrets.token_urlsafe(32),
        }
        self._save(state)
        return self._public(state)

    def _public(self, state):
        sid = state["id"]
        return {k: state[k] for k in ("id", "owner", "branch", "status", "base_sha")} | {
            "view_path": f"/preview/{state['view_token']}/",
            "editor_path": f"/preview/{state['edit_token']}/gallery-editor.html",
            "worktree": state["worktree"],
        }

    def status(self, sid, owner):
        state = self._load(sid, owner)
        result = self._public(state)
        if state["status"] == "active":
            result["changes"] = _git(state["worktree"], "status", "--porcelain", "--", "assets")
        return result

    def from_token(self, token, *, editing=False):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            raise ValueError("Invalid preview capability")
        for path in self.base.glob("*.json"):
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("status") != "active":
                continue
            accepted = state.get("edit_token") if editing else None
            if editing:
                valid = secrets.compare_digest(token, accepted or "")
            else:
                valid = (secrets.compare_digest(token, state.get("view_token", "")) or
                         secrets.compare_digest(token, state.get("edit_token", "")))
            if valid:
                return state
        raise ValueError("Preview capability invalid or expired")

    def _collection(self, state, collection):
        if not isinstance(collection, str) or not _COLLECTION.fullmatch(collection) or collection in (".", ".."):
            raise ValueError("Invalid collection")
        root = Path(state["worktree"])
        folder = _within(root, root / "assets" / collection)
        gallery = _within(root, folder / "gallery.txt")
        if not gallery.is_file() or gallery.is_symlink():
            raise ValueError("Unknown collection")
        return folder, gallery

    @staticmethod
    def _gallery_sha(gallery):
        return hashlib.sha256(gallery.read_bytes()).hexdigest()

    def gallery(self, sid, owner, collection):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        folder, gallery = self._collection(state, collection)
        return {"images": gallery.read_text(encoding="utf-8").splitlines(),
                "sha256": self._gallery_sha(gallery)}

    def save_gallery(self, sid, owner, collection, images, expected_sha=None):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        folder, gallery = self._collection(state, collection)
        if not isinstance(images, list) or len(images) > 500:
            raise ValueError("images must be a list of up to 500 filenames")
        seen = set()
        for name in images:
            if not isinstance(name, str) or not _FILENAME.fullmatch(name) or name in (".", ".."):
                raise ValueError("Invalid gallery image filename")
            if name.casefold() in seen:
                raise ValueError("Gallery filenames must be unique")
            seen.add(name.casefold())
            file = _within(folder, folder / name)
            if not file.is_file() or file.is_symlink():
                raise ValueError(f"Gallery image not found: {name}")
        current = self._gallery_sha(gallery)
        if expected_sha is not None and expected_sha != current:
            raise ValueError("Gallery changed since it was loaded; refresh before saving")
        new_content = "\\n".join(images) + ("\\n" if images else "")
        tmp = gallery.with_name(".gallery-" + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(new_content, encoding="utf-8")
            tmp.replace(gallery)
        finally:
            tmp.unlink(missing_ok=True)
        return {"collection": collection, "count": len(images),
                "sha256": self._gallery_sha(gallery)}

    def publish(self, sid, owner):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        wt = Path(state["worktree"])
        # Protect the user from committing unexpected non-gallery content.
        dirty = _git(wt, "status", "--porcelain", "--untracked-files=all")
        for line in dirty.splitlines():
            changed = line[3:]
            if " -> " in changed:
                raise ValueError("Renamed paths are not supported in Phase 1")
            if not changed.startswith("assets/"):
                raise ValueError(f"Unexpected non-gallery change: {changed}")
        if not dirty:
            raise ValueError("Nothing to publish")
        _git(wt, "add", "-A", "--", "assets")
        _git(wt, "commit", "-m", f"Marie-Parie preview {sid[:10]}")
        # Fast-forward only. Refuse silently overwriting newer staging changes.
        _git(wt, "push", "origin", "HEAD:refs/heads/staging")
        state["status"] = "published"
        self._save(state)
        return {"status": "published", "branch": state["branch"],
                "commit": _git(wt, "rev-parse", "HEAD")}

    def cancel(self, sid, owner):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Only active sessions can be cancelled")
        _git(self.repo, "worktree", "remove", "--force", state["worktree"])
        _git(self.repo, "branch", "-D", state["branch"])
        state["status"] = "cancelled"
        self._save(state)
        return {"status": "cancelled", "id": sid}
