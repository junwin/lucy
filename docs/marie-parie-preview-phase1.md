# Marie-Parie Preview Sessions — Phase 1

A private, temporary review site for Arla, running **inside Lucy's existing Flask
server**. This is a first step toward MCP; the lifecycle is implemented in
\`src/marie_preview.py\` independently of the agent handler and Flask transport.

## Workflow

1. Gwen calls \`marie_preview(action="create")\`. Lucy fetches remote
   \`staging\` and creates a new \`preview/marie-parie/<owner>-<id>\` branch
   in an isolated Git worktree under Lucy's storage.
2. Gwen prepares web images using the existing image-description virtualenv.
   The media publisher is pointed at the returned **worktree** path using
   \`--repo\`; do **not** use \`--commit\` or \`--push\` at this point.
3. Gwen gives Arla the returned \`view_path\`, resolved relative to the **same
   HTTPS origin** where her Lucy client is connected through ngrok.
   \`editor_path\` opens the gallery editor with an added
   **Save to Lucy preview** action. Its order and delete controls do not
   delete original image files.
4. Arla may ask Gwen to edit \`gallery.txt\` through
   \`marie_preview(action="gallery")\` followed by
   \`marie_preview(action="save_gallery")\`, or use the visual editor.
5. On **explicit approval**, Gwen calls \`marie_preview(action="publish")\`.
   Lucy commits only \`assets/\` changes on the session branch and pushes
   the result to \`staging\` without force. Existing Cloudflare staging
   deployment is responsible for the shared review site Heidi sees.
6. On explicit cancellation, \`marie_preview(action="cancel")\` removes
   the *local* worktree and branch. The preview URL stops working.

A user may reset Gwen's chat or return later. \`marie_preview(action="list")\`
finds the user's sessions without relying on chat history, and
\`action="status"\` reports the selected branch and local changes.

## Troubleshooting / sharing the work

If an author asks for help, \`marie_preview(action="share")\` commits and
pushes only the session's \`preview/marie-parie/...\` branch to GitHub.
**It does not modify staging**. Someone with GitHub access can then
inspect the preview branch. Its remote branch is deliberately retained
after publish/cancel for investigation; cleanup is a separate manual step.

## Browser capabilities

The read-only \`view_path\` and editable \`editor_path\` each contain a
high-entropy secret. These URLs are session capabilities, not public links.
The web routes bypass Lucy's normal API-key check *only* under
\`/preview/<token>/\`; the blueprint validates the token on each request.
A read-only token cannot save galleries. Tokens become invalid when a session
is published or cancelled. Do not share an editor link with Heidi.

The preview follows Lucy's ngrok HTTP origin; if the web client and Flask API
are on different origins, configure the existing frontend proxy to forward
\`/preview/*\` requests to Lucy before testing remotely. No extra ngrok tunnel
should be required when they already share an origin.

**Security and Phase 1 limitations**:
- This is a private UAT facility, not yet a multi-user public CMS.
- Review links are bearer capabilities; treat them as confidential.
- A local Git identity and \`origin\` push permissions are required for
  publish/share operations.
- Staging deployment may take time; Lucy's successful Git push does not
  prove the Cloudflare deployment succeeded.
- Never submit real customer information through a preview contact form.
- Only existing gallery folders and existing JPG/PNG assets can be listed
  by the editor. New photos must first be prepared and copied into the
  preview worktree by the media pipeline.
- An existing session cannot overwrite remote staging if it has moved on;
  Git rejects the non-fast-forward push. Escalate for review rather than
  forcing the push.
- A session's published remote preview branch is intentionally retained,
  but the original Lucy worktree is not automatically pruned on publish.
- Phase 1 creates **no** production deployment or automatic staging-to-main merge.

## Test in Lucy's virtualenv

\`\`\`bash
cd ~/src/repos/lucy
git fetch origin
git switch feature/marie-parie-preview
source .venv/bin/activate
pytest -q tests/test_marie_preview.py
\`\`\`

The media-publisher compatibility change lives on the separate
\`image_description\` feature branch
\`feature/marie-parie-media-workflow\`. Update both local checkouts.

## Gwen's lifecycle

- **Prepare a preview**: create session, export uploads, resize and describe
  photographs, review filenames, publish prepared files locally into the
  returned preview worktree, show temporary preview/editor links.
- **Make changes**: gallery read/save, or visual editor Save to Lucy preview.
- **Publish**: only with explicit consent; then give the usual Cloudflare
  staging link for Heidi.
- **Cancel**: explicit consent; remove worktree and revoke local preview URL.
- **Ask for help**: share preview branch (not staging) for GitHub inspection.

For development and debugging see \`src/marie_preview.py\`,
\`src/marie_preview_web.py\`, and \`tests/test_marie_preview.py\`.
