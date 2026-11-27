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
from urllib.parse import urlsplit

_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
_COLLECTION = re.compile(r"^[^/\\]+$")
_FILENAME = re.compile(r"^[^/\\]+\.(?:jpg|jpeg|png)$", re.I)


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
        self.config = config
        self.repos_root = Path(roots["repos"]).resolve()
        self.repo = self.repos_root / "marie-parie-web"
        self.worktrees = self.repos_root / "marie-parie-previews"
        if not (self.repo / ".git").exists():
            raise ValueError("Marie-Parie web Git checkout not found")
        storage = Path(config.get("storage_root_path", "/home/junwin/lucy_storage"))
        namespace = config.get("storage_namespace", "data")
        self.base = storage / namespace / "marie_parie_previews"
        explicit_origin = str(config.get("preview_public_base_url", "") or "").strip().rstrip("/")
        if explicit_origin:
            parsed = urlsplit(explicit_origin)
            if (parsed.scheme not in ("http", "https") or not parsed.netloc
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                    or parsed.username or parsed.password):
                raise ValueError("preview_public_base_url must be an HTTP(S) origin")
            self.preview_origin = explicit_origin
        else:
            port = int(config.get("port", 5000))
            if not 1 <= port <= 65535:
                raise ValueError("Invalid Lucy port")
            self.preview_origin = f"http://localhost:{port}"
        self.base.mkdir(parents=True, exist_ok=True)
        self.worktrees.mkdir(parents=True, exist_ok=True)

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
        worktree = self.worktrees / ("session-" + sid)
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
            "view_url": f"{self.preview_origin}/preview/{state['view_token']}/",
            "editor_url": f"{self.preview_origin}/preview/{state['edit_token']}/gallery-editor.html",
            "worktree": state["worktree"],
        }

    def list(self, owner):
        """Return owned sessions without depending on Lucy chat history."""
        results = []
        for path in sorted(self.base.glob("*.json")):
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("owner") == owner:
                results.append(self._public(state))
        return {"sessions": results, "count": len(results)}

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
        new_content = "\n".join(images) + ("\n" if images else "")
        tmp = gallery.with_name(".gallery-" + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(new_content, encoding="utf-8")
            tmp.replace(gallery)
        finally:
            tmp.unlink(missing_ok=True)
        return {"collection": collection, "count": len(images),
                "sha256": self._gallery_sha(gallery)}

    def import_web_batch(self, sid, owner, collection, batch_id, replace=False, expected_sha=None):
        """Copy this exact prepared batch into a preview, then update gallery.

        Unlike save_gallery, this action transfers image BYTES and is safe when
        an older batch uses the same filenames. All copied file paths stay inside
        the preview collection; uploaded originals are never modified.
        """
        if not isinstance(batch_id, str) or not re.fullmatch(r"batch-[0-9a-f]{12}", batch_id):
            raise ValueError("Use the batch-xxxxxxxxxxxx ID returned by attachments export")
        if type(replace) is not bool:
            raise ValueError("replace must be true or false")
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        folder, gallery = self._collection(state, collection)
        current_sha = self._gallery_sha(gallery)
        if expected_sha is not None and current_sha != expected_sha:
            raise ValueError("Gallery changed since it was loaded; refresh before importing")

        roots = self.config.get("external_roots") or {}
        pictures = roots.get("pictures") if isinstance(roots, dict) else None
        if not pictures:
            raise ValueError("external_roots.pictures is required for batch import")
        workspace = Path(pictures).resolve() / "marie-parie" / "prepared" / "web"
        source = (workspace / batch_id).resolve()
        if not source.is_relative_to(workspace) or not source.is_dir():
            raise ValueError(f"Prepared web batch not found: {batch_id}")
        photos = sorted(
            (p for p in source.iterdir() if p.suffix.lower() == ".jpg" and p.is_file() and not p.is_symlink()),
            key=lambda p: p.name.casefold())
        if not photos:
            raise ValueError("The selected batch has no prepared web JPEGs")
        # A batch must not have duplicate names, including case-only variants.
        if len({p.name.casefold() for p in photos}) != len(photos):
            raise ValueError("Prepared batch has duplicate image filenames")
        existing_names = {p.name.casefold() for p in folder.iterdir() if p.is_file()}
        planned = []
        used = set()
        for photo in photos:
            if not _FILENAME.fullmatch(photo.name):
                raise ValueError(f"Unsafe prepared image filename: {photo.name}")
            digest = hashlib.sha256(photo.read_bytes()).hexdigest()
            name = photo.name
            target = _within(folder, folder / name)
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise ValueError(f"Unsafe gallery target: {name}")
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    # Content-addressed suffix disambiguates successive uploads
                    # of identically named, but different, photographs.
                    stem = photo.stem
                    for count in range(8, 65, 4):
                        proposal = f"{stem}-{digest[:count]}.jpg"
                        candidate = _within(folder, folder / proposal)
                        if candidate.exists() and (candidate.is_symlink() or
                                hashlib.sha256(candidate.read_bytes()).hexdigest() != digest):
                            continue
                        name = proposal
                        target = candidate
                        break
                    else:
                        raise ValueError(f"Could not find a unique destination for {photo.name}")
            if name.casefold() in used:
                raise ValueError(f"Conflicting destinations in batch: {name}")
            if name.casefold() in existing_names and not target.exists():
                raise ValueError(f"Case-insensitive filename collision: {name}")
            used.add(name.casefold())
            planned.append((photo, target, name))

        # Replacing means replacing gallery DISPLAY entries, not deleting
        # old files; removing entries before the new files arrive is unsafe.
        current = [name for name in gallery.read_text(encoding="utf-8").splitlines() if name]
        new_names = [name for _, _, name in planned]
        ordered = list(new_names)
        if not replace:
            seen = {name.casefold() for name in ordered}
            ordered.extend(name for name in current if name.casefold() not in seen and not seen.add(name.casefold()))
        created = []
        try:
            for photo, target, _ in planned:
                if not target.exists():
                    # Exclusive create avoids overwriting an image from another
                    # preview batch if concurrent work happens in this folder.
                    with photo.open("rb") as reader, target.open("xb") as writer:
                        created.append(target)
                        shutil.copyfileobj(reader, writer)
            if self._gallery_sha(gallery) != current_sha:
                raise ValueError("Gallery changed during import; retry")
            content = "\\n".join(ordered) + ("\\n" if ordered else "")
            tmp = gallery.with_name(".gallery-" + uuid.uuid4().hex + ".tmp")
            try:
                tmp.write_text(content, encoding="utf-8")
                tmp.replace(gallery)
            finally:
                tmp.unlink(missing_ok=True)
        except Exception:
            for target in created:
                target.unlink(missing_ok=True)
            raise
        return {"collection": collection, "batch_id": batch_id,
                "imported": new_names, "count": len(new_names),
                "gallery_count": len(ordered), "replace": replace,
                "sha256": self._gallery_sha(gallery)}

    def _safe_changes(self, wt):
        """Inspect Git's NUL-separated paths, including names containing spaces."""
        result = subprocess.run(
            ["git", "-C", str(wt), "status", "--porcelain", "-z",
             "--untracked-files=all"],
            check=True, capture_output=True, text=True,
        ).stdout
        records = [record for record in result.split("\0") if record]
        for record in records:
            if len(record) < 4:
                raise ValueError("Malformed Git status output")
            status, changed = record[:2], record[3:]
            if "R" in status or "C" in status:
                raise ValueError("Renamed/copied paths are not supported in Phase 1")
            if not changed.startswith("assets/"):
                raise ValueError(f"Unexpected non-gallery change: {changed}")
        return bool(records)

    def _commit_assets(self, state):
        wt = Path(state["worktree"])
        dirty = self._safe_changes(wt)
        if dirty:
            _git(wt, "add", "-A", "--", "assets")
            _git(wt, "commit", "-m", f"Marie-Parie preview {state['id'][:10]}")
        return _git(wt, "rev-parse", "HEAD")

    def share(self, sid, owner):
        """Push the preview branch to GitHub for troubleshooting, not staging."""
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        commit = self._commit_assets(state)
        if commit == state["base_sha"]:
            raise ValueError("No changes to share yet")
        _git(state["worktree"], "push", "origin",
             f"HEAD:refs/heads/{state['branch']}")
        return {"status": "active", "branch": state["branch"], "commit": commit,
                "shared": True}

    def publish(self, sid, owner):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Preview session is closed")
        commit = self._commit_assets(state)
        if commit == state["base_sha"]:
            raise ValueError("Nothing to publish")
        # Fast-forward only. Refuse silently overwriting newer staging changes.
        _git(state["worktree"], "push", "origin", "HEAD:refs/heads/staging")
        state["status"] = "published"
        self._save(state)
        return {"status": "published", "branch": state["branch"], "commit": commit}

    def cancel(self, sid, owner):
        state = self._load(sid, owner)
        if state["status"] != "active":
            raise ValueError("Only active sessions can be cancelled")
        _git(self.repo, "worktree", "remove", "--force", state["worktree"])
        _git(self.repo, "branch", "-D", state["branch"])
        state["status"] = "cancelled"
        self._save(state)
        return {"status": "cancelled", "id": sid}
