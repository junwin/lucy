# Export chat uploads to Marie-Parie workflows

Lucy agents with the existing `attachments` tool may now use
`action="export"` to copy uploaded images from their current conversation
into a **fresh batch subfolder** under an approved destination. Original
uploads remain in Lucy storage.

## Configure a local destination

Add this to your **local config override** (not an agent message or
GitHub-tracked configuration containing machine-specific paths):

```json
{
  "attachment_export_destinations": {
    "marie_parie_incoming": "/home/junwin/Pictures/incomming-mp"
  }
}
```

The corresponding `config.local.json` is loaded and deep-merged by
`ConfigManager`. Reload/restart Lucy after changing configuration.

## Agent workflow

1. Use `attachments` action `list` to find the images in the current
   conversation. Check filenames and count against the user's request.
2. Invoke `attachments` action `export` for the selected IDs in the
   desired order, with destination alias `marie_parie_incoming` and collision
   `rename`. The tool definition also requires the legacy fields
   `image_id=""`, `offset=0`, `count=10`.
3. Use **`batch_directory` returned by the tool**, never the parent
   `incomming-mp`, as input to the Marie-Parie scripts. This avoids
   accidentally processing earlier test images.
4. Work in `/home/junwin/src/repos/image-description` with the
   `.venv/bin/marie-resize`, `.venv/bin/marie-video`, etc executables.
5. Show the result through `serve_video` or `serve_image` and ask for
   approval before publishing to the website.

Example export arguments:

```json
{
  "action": "export",
  "image_id": "",
  "offset": 0,
  "count": 10,
  "image_ids": ["IMAGE_UUID_1", "IMAGE_UUID_2"],
  "destination": "marie_parie_incoming",
  "collision": "rename"
}
```

The actual values must come from an earlier `attachments list` result.

## Supported files and limitations

- JPEG, PNG and WebP images only; GIF is intentionally excluded.
- 1–20 images per export, currently from the active conversation.
- Export requires the image to belong to the active account and chat.
- Destination is a configured alias; arbitrary filesystem paths are refused.
- An export always makes a new `batch-...` subfolder and never overwrites
  files in previous batches. Duplicate filenames within a batch are renamed
  with an image-ID suffix by default; `collision=fail` rejects them.
- Export is a copy operation. No original uploads are moved or removed.
- This handler does not resize, publish or make API calls.

## Run tests

```bash
cd ~/src/repos/lucy
git switch feature/attachment-export
source .venv/bin/activate
pytest -q tests/test_reusable_attachments.py tests/test_attachment_export.py
```

Manual acceptance test: upload four photographs in Gwen's chat, ask for
a Reel using those uploads, and confirm Gwen stages the four selected images
into the returned batch folder before running `marie-resize` and
`marie-video`. Gwen should not silently switch to older local photographs.
