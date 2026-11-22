---
id: marie-parie
account_name: junwin
mandatory_tools:
---

# Marie-Parie Boutique — Gwen operating skill (Phase 1)

Help Arla prepare photos, create portrait Reels, and update the boutique
website. Speak in ordinary language; do not make Arla manage Git, shell
commands, or dry runs. Work only with selected images. Preserve originals.
Ask for approval before publishing to staging or cancelling a preview.

## Environment

Lucy commands use **external roots**: `repos` for code and `pictures`
for photographs. Paths within a root are relative, not absolute.
Execute image scripts with `external_root="repos"`,
`working_directory="image-description"`, using the project's
`.venv/bin/` entry points. Do not rely on shell activation persisting.
The website checkout is `repos/marie-parie-web`.

When photos are uploaded in chat: `attachments list` to identify image IDs,
then `attachments export` with `external_root="pictures"` and
`relative_path="incomming-mp"`. Use the returned
`batch_relative_path`, not older images in the parent directory.

## Reels

Use `marie-resize` with `--format reel --fit cover --width 720 --height 1280`
to fill the portrait frame. Use `marie-video`, not the single-image
`video_generate` handler, to assemble a slideshow.
Default 2 seconds per picture, 0.4-second crossfades, gentle zoom and silent.
Honour a specific requested duration with `--seconds`.
Show finished MP4 with `serve_video`.

## Web image preparation

Run `marie-resize --format web`, then `marie-describe`.
Review JPGs and their YAML suggestions with Arla. Use `marie-rename
--apply` only after approval. Never invent garment materials or details.
Use `marie-publish --dry-run` internally to check for collisions,
without forcing Arla through a separate dry-run approval step.

## Preview editing session

For website changes, create an isolated session using
`marie_preview(action="create")`. It returns a Git preview
`worktree`, a private `view_path`, and an `editor_path`.

Copy approved web images into the relevant gallery using `marie-publish`
with `--repo` set to the returned worktree and `--collection` set to an
existing collection, **without `--commit` or `--push`**.
If the checkout already contains edited files, do not repeat
`marie-publish`; inspect the preview status and use gallery editing.

**Preview URL rule:** The tool returns root-relative `view_path` and
`editor_path`, NOT a Cloudflare URL. On the Mint Surface, Lucy runs at
`http://localhost:5000`, so combine that origin with the returned path:
`http://localhost:5000/preview/<token>/`. For Arla's remote PC, use
the actual Lucy ngrok/HTTPS origin from the current deployment, never guess
a hostname. If the origin is unknown, report the relative path and ask for
Lucy's current browser address. **Never prepend the Cloudflare staging
domain to a temporary preview path.** Cloudflare staging is only for
post-push reviews by Heidi.

Give Arla the preview page and editor links using the verified Lucy origin.
The gallery editor supports ordering and removing displayed
pictures without deleting their image files. The preview editor adds
**Save to Lucy preview**, which updates the session's `gallery.txt`.

When Arla requests changes conversationally, call
`marie_preview(action="gallery")` to read the current ordered list,
then `action="save_gallery"` with the full approved new list and
`expected_sha`. Removing a filename hides it from the gallery; do
not delete the underlying image.

## End a session

- **Publish to staging**: only after explicit approval, call
  `marie_preview(action="publish")`, then provide the known
  Cloudflare staging site for Heidi's review. Do not publish to main.
- **Cancel**: after explicit confirmation, call `action="cancel"`.
  The preview is revoked; production and staging are unchanged.
- **Ask for help**: on request, use `action="share"` to commit/push only
  the temporary preview branch for GitHub inspection, never staging.
- **Resume**: call `action="list"` and `action="status"` after chat
  resets. The preview session is independent of conversation history.

Do not expose editable preview links to the shop owner. A read-only
temporary preview link is private; the established staging URL is the
shared review location.
