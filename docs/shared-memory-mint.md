# Shared memory configuration on Mint

Lucy can use the same galet-memory JSON already tested through galet-tools MCP.
The opt-in setting is `memory_config_path`, in Lucy's local config, or
`GALET_MEMORY_CONFIG_PATH` when the setting is absent. Galet owns credentials
through its existing `GALET_CREDENTIAL_PATH` lookup.

## Install and select the tested configuration

From the Mint Lucy checkout, activate its existing virtual environment, switch
to `shared-memory-runtime`, and install the updated requirements:

```bash
git fetch origin
git switch shared-memory-runtime
# Activate your existing Lucy environment first (venv or .venv).
python -m pip install -r requirements.txt
python -m pytest
```

The requirements use galet 0.1.26, galet-memory 0.1.28 and a reviewed immutable
galet-tools revision containing the focused episodic operations. The exact tools
revision is temporary until a coordinated PyPI release is available.

Merge this property into the existing `config.local.json`; retain the other
Mint-specific settings. Do not replace the whole local config with this snippet.
`examples/config.local.memory-mint.json` contains the same override:

```json
{
  "memory_config_path": "/home/junwin/src/repos/galet-tools/galet-memory-mcp.json"
}
```

Reuse the exact memory configuration that worked with MCP. Check its paths:

- Semantic database: `/home/junwin/lucy_storage/data/embeddings-v3.sqlite`,
  `metadata_version:3`, `create:false` after deploying the verified migrated copy.
- Episodic database: the exact existing file whose sessions you verified in MCP,
  with `create:false`. Do not choose it merely from a v2/v3 filename: the semantic
  migration does not require an episodic migration or rename.
- Procedural root: `/home/junwin/lucy_storage/data` and the explicit `contexts`
  and `skills` layout already tested. This controls prompts, tools and context APIs.
- Digest directory: the configured existing directory, normally `data/digests`.
- Working database: the configured file under `data`; creation remains explicit.

All three main components (semantic, episodic and procedural), including an
explicit episodic `digests_directory`, are required for Lucy shared mode. Working memory is optional internal state on the runtime.
The selected memory config owns memory roots, stores, layouts and embedding
profile; Lucy's old memory-specific settings are used only without shared mode.
Lucy file tools, attachment storage and tasklist storage continue to use their
normal Lucy settings. The legacy embedding store is not opened for configured
recall or curation, and is not converted automatically.

Restart Lucy with the credential environment present:

```bash
export GALET_CREDENTIAL_PATH=/home/junwin/credential
python app.py
```

Startup logs `lucy_memory_ready` with the selected config, semantic metadata
version and episodic database. A selected invalid config stops startup; it does
not fall back to the old store. Memory configuration changes require a process
restart. The runtime closes at process exit, not after each Flask request.

## Focused checks before wider use

1. Verify the same existing chats appear in the Mint client and read their events.
2. In a fresh test chat, use a reading context with `search_namespaces` including
   `books` or `vol_7`. Ask about the known Fosse or Tyntesfield note. Check the
   recalled source path and `backend:vector` in a `semantic_memory` call.
3. Check global/account context precedence and a known imported skill in a prompt.
4. Enable `episodic_list_sessions`, `episodic_get_session` and
   `episodic_get_recent_events` for a test agent if desired. Registration does not
   grant permission; normal agent/context restrictions still apply.
5. Append a test exchange, archive it, then test digest reads/search and reset.
   Archive/reset operations retain original events. If you invalidate a test
   exchange, its derived digest must disappear from digest retrieval.

Configured archive publication writes V3 digest resource locators with the selected
embedding profile, source event provenance and authorized root-relative path.
Digest search checks account ownership/invalidation and resolves the file again
on each read. Digest recall uses the episodic digest channel; generic V3 semantic
recall continues to support files/inline resources and does not turn digests into
ordinary files. Missing or unauthorized files do not fall back to stored text.

The legacy standalone ingestion scripts still use their own legacy embedding
configuration; do not point them at the V3 database. Use the configured
`galet_memory.build_memory(...).ingest_file(...)` API for V3 ingestion. This
integration does not migrate those scripts or existing deferred legacy records.

## Returning to the previous setup

Stop Lucy, remove the `memory_config_path` override and unset
`GALET_MEMORY_CONFIG_PATH`, then restart. The original legacy settings and V2
embedding database remain available. Writes already made to the selected shared
episodic/procedural stores remain there; changing configuration does not undo them.
