# Reusable chat images

An image is uploaded once through `/upload/image`. Subsequent image edits and
video generations reuse its UUID and the original stored bytes. This does not
require a gptChum payload change: `/ask` already receives `image_ids`.

## Saved references

Both streaming and non-streaming function-calling turns store ordered
`image_ids` and `file_ids` in the user event's metadata. The message text stays
unchanged. References share that turn's `correlation_id`; bytes and base64 are
never saved in these fields. As with other conversation history, the agent
must have `save_responses` enabled.

Generated image events already store `image_id`. Successful video generation
also carries `source_image_id` through the video event and saved history.
Non-streaming calls now retain their media events as well as the final text.

## Lookup tool

`attachments` uses the injected account and current conversation, not a
model-supplied account or session. It supports:

```json
{"action":"list","image_id":"","offset":0,"count":10}
```

```json
{"action":"get","image_id":"<selected-uuid>","offset":0,"count":1}
```

List returns newest turns first, preserving image order within each turn.
Each image includes its original filename, position, origin, event ID,
correlation IDs, MIME type, preview URL and relative storage path. Its
`last_video_id`, when present, links it to the latest saved video produced
from that still. Results contain at most 20 images per page; `next_offset`
allows older pages to be requested.

Lookup reads the visible transcript rather than the recent prompt window.
Archived images remain reusable; invalidated exchanges are excluded. A UUID
must both occur in that chat and resolve to an existing account-owned image
with matching metadata. Missing files, invalid references and foreign images
are excluded. Reopening the session or switching its agent does not change
these references.

Use `image_id` with `video_generate`, or `[image_id]` with
`image_generate.image_ids`. Show a candidate with `serve_image` using
`location="storage"` and its returned path. Multiple plausible matches require
clarification; the latest image is not automatically the intended source.

The built-in agents that already allow `video_generate` now allow
`attachments`. Custom or account-specific agent configurations must also
include `attachments` in `allowed_tools`. The registry exposes it for normal
discovery and activation; prompt guidance explains reuse and ambiguity.

## Manual video test

1. Start Lucy with this branch, keeping the normal video provider configuration.
2. In a saved chat with Lucy or Lumia, upload a JPG/PNG and request a short video.
3. Without attaching anything, ask: "Use the same photograph again, but make
   the turn slower and keep the clothes unchanged."
4. Check that Lucy uses the original image UUID with the revised prompt and
   delivers another MP4 through the existing video card.
5. Reopen the chat and repeat. Upload two photos and check that an ambiguous
   request prompts for the intended photo instead of silently choosing one.

## First iteration boundaries

This branch delivers reusable uploaded/generated stills for video production
and image editing. Website asset copying, batch replacement mappings and a
gptChum thumbnail picker are separate follow-up work. Lookup currently returns
images only; `file_ids` are persisted for future general-file support.

Old user messages saved before this change lack attachment IDs and cannot be
reconstructed reliably. Existing generated-image events with valid IDs can
be reused. Old video events lack source provenance. No schema migration or
Galet package upgrade is needed.

Tests cover both processor modes, ordered metadata, reopen and lookup beyond
120 later messages, video retries using the same bytes, generated references,
pagination, account/session isolation, invalidation and missing files. Video
provider responses are mocked; automated tests do not purchase generation.
