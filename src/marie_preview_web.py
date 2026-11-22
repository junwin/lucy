"""Temporary Marie-Parie preview site, same origin as Lucy's ngrok client.

Each URL has a random, revocable capability. Read-only URLs cannot save edits.
Never mount an unrestricted worktree as a static directory.
"""
from pathlib import Path
from flask import Blueprint, Response, jsonify, request, send_file

from src.marie_preview import MariePreviewService

preview_blueprint = Blueprint("marie_preview", __name__)


def _service():
    from flask import current_app
    return MariePreviewService(current_app.config["lucy_config"])


def _error(message, status=400):
    return jsonify({"ok": False, "error": str(message)}), status


def _editor_patch():
    # Inject a small, same-origin adapter into the existing editor.
    # The editor's own drag/order/undo/download behaviour remains unchanged.
    return r"""
<script>
(() => {
  'use strict';
  const save = document.createElement('button');
  save.type = 'button';
  save.className = 'primary';
  save.textContent = 'Save to Lucy preview';
  document.querySelector('#download').after(save);
  save.addEventListener('click', async () => {
    if (!current || busy) return;
    const collection = collections[Number(document.querySelector('#collection').value)].folder;
    const endpoint = './api/gallery/' + encodeURIComponent(collection);
    save.disabled = true;
    tell('Saving changes to your preview...');
    try {
      const oldResponse = await fetch(endpoint, {cache: 'no-store'});
      if (!oldResponse.ok) throw new Error('Could not check the current gallery');
      const old = await oldResponse.json();
      if (serialise(parse(old.images.join('\n') + '\n')) !== serialise(current.original)) {
        throw new Error('The gallery changed in another window. Refresh before saving.');
      }
      const response = await fetch(endpoint, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          images: current.entries.map(entry => entry.file),
          expected_sha: old.sha256
        })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'Save failed');
      current.original = clone(current.entries);
      current.history = [];
      tell('Saved to Lucy preview. Refresh the boutique page to review.');
      controls();
    } catch (error) {
      tell('Could not save: ' + error.message);
    } finally { save.disabled = false; }
  });
})();
</script>
"""


@preview_blueprint.route("/preview/<token>/api/gallery/<path:collection>", methods=["GET", "PUT"])
def preview_gallery(token, collection):
    try:
        service = _service()
        state = service.from_token(token, editing=request.method == "PUT")
        if request.method == "GET":
            result = service.gallery(state["id"], state["owner"], collection)
            return jsonify(result)
        if not request.is_json:
            return _error("Expected JSON", 415)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Invalid JSON")
        result = service.save_gallery(
            state["id"], state["owner"], collection,
            payload.get("images"), payload.get("expected_sha"),
        )
        return jsonify({"ok": True, **result})
    except (ValueError, OSError) as exc:
        return _error(exc, 403)


@preview_blueprint.route("/preview/<token>/", defaults={"file_path": "index.html"}, methods=["GET"])
@preview_blueprint.route("/preview/<token>/<path:file_path>", methods=["GET"])
def preview_static(token, file_path):
    try:
        service = _service()
        state = service.from_token(token)
        root = Path(state["worktree"]).resolve()
        if not file_path or any(part.startswith(".") for part in Path(file_path).parts):
            return _error("File not found", 404)
        file = (root / file_path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            return _error("File not found", 404)
        if file_path == "gallery-editor.html":
            html = file.read_text(encoding="utf-8")
            html = html.replace("</body>", _editor_patch() + "\n</body>")
            response = Response(html, content_type="text/html; charset=utf-8")
        else:
            response = send_file(file)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response
    except (ValueError, OSError) as exc:
        return _error(exc, 404)
