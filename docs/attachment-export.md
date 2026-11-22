# Export chat-uploaded images using Lucy external roots

Agents with the `attachments` handler can copy images owned by the current
account and conversation into an approved `external_roots` directory. Lucy
creates a fresh batch subfolder and retains original chat uploads.

## Configuration

This uses Lucy's **existing** `external_roots` setting. For example:

```json
{
  "external_roots": {
    "pictures": "/home/junwin/Pictures",
    "repos": "/home/junwin/src/repos"
  }
}
```

There is **no separate `attachment_export_destinations` setting**.
`external_root` names a configured root and `relative_path` selects
a subfolder inside that root. Absolute paths, traversal and unknown roots
are rejected. The export handler creates an isolated `batch-...` folder
under the chosen relative path.

## Conversation workflow

1. Call `attachments` with `action="list"` to obtain the IDs and filenames
   of uploaded photographs. Confirm selection if ambiguous.
2. Call `attachments` with `action="export"` using those exact IDs,
   `external_root="pictures"`, `relative_path="incomming-mp"`,
   and `collision="rename"`.
3. Use `batch_relative_path` returned from export as the *input directory*
   when running Marie-Parie scripts with `execute_command`:
   root `pictures` plus the returned relative path (for example,
   `incomming-mp/batch-123...`). Do not use the parent incoming folder.
4. Work in the `image-description` checkout under the external `repos`
   root and use the project's `.venv/bin/marie-resize` and
   `.venv/bin/marie-video` scripts.
5. Present the resulting video using `serve_video`.

Example of **export** arguments (replace placeholders with IDs from list):

```json
{
  "action": "export",
  "image_id": "",
  "offset": 0,
  "count": 10,
  "image_ids": ["IMAGE_UUID_1", "IMAGE_UUID_2"],
  "external_root": "pictures",
  "relative_path": "incomming-mp",
  "collision": "rename"
}
```

For `list` and `get`, unused `image_ids`, `external_root`,
`relative_path`, and `collision` should be `null` when required by
the strict tool schema.

The export result returns:

- `external_root`: approved root name
- `relative_path`: selected destination directory under the root
- `batch_relative_path`: new directory **relative to the root**
- `batch_directory`: resolved absolute directory (for display/diagnostics)
- `exported`: selected source image IDs, filenames, and copied paths

## Limitations

- JPEG, PNG and WebP only, maximum 20 images per request.
- Only images previously attached to the *current conversation* are eligible.
- Uploads are copied; originals are not moved or modified.
- Export creates a separate directory per request. Filenames are sanitized.
- Duplicate names get an image-ID suffix by default, or fail with
  `collision="fail"`.
- The caller can select any subdirectory of an **approved** external root;
  this permission is no narrower than the approved root itself.
- No video creation, publishing, remote upload or image resize is performed
  by the export handler.

## Tests

```bash
cd ~/src/repos/lucy
git switch feature/attachment-export
source .venv/bin/activate
pytest -q tests/test_reusable_attachments.py tests/test_attachment_export.py
```

Manual acceptance: ask Gwen to create a Reel from three *chat-uploaded*
photographs, export them to `pictures/incomming-mp`, and check that the
returned `batch_relative_path` (not older photos directly in
`incomming-mp`) is processed. No new configuration alias is needed.
