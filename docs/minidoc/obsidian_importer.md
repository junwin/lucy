---
tags:
  - obsidian_import
  - lucyproject
  - indexed_records
---


# Obsidian importer (indexer)

This importer reads `*.md` files from an Obsidian vault (or any folder) and upserts them into Lucy’s document store as `DocumentRef` records.

## Where the code lives

- Library code (reusable): `src/utils/obsidian_importer.py`
  - Main entrypoint: `index_obsidian_vault(storage, account_name, vault_path, kind="obsidian_note", max_files=None)`
- CLI wrapper (run from terminal): `scripts/obsidian_index.py`

### Recommended placement going forward

- Keep the reusable importer in `src/utils/obsidian_importer.py` (or, if you want to be stricter about boundaries later, move it to something like `src/ingest/obsidian.py`).
- Treat the CLI as a *script/entrypoint*.
  - For developer use, run the CLI from the repo root as `python scripts/obsidian_index.py`.
  - Environment variables are supported to avoid hard-coded paths (see below).

## What it writes

For each markdown file, it creates a `DocumentRef` with:

- `id`: stable SHA-256 hash of the file path (so re-running won’t create duplicates)
- `account_name`: whatever you pass on the CLI
- `path`: full path to the markdown file
- `kind`: defaults to `"obsidian_note"`
- `title`: filename stem
- `tags`: parsed from YAML frontmatter `tags:` (if present)
- `metadata`:
  - `vault`: vault folder name
  - `relative_path`: path relative to the vault root

## How to run (CLI)

From the repo root:

```bash
python scripts/obsidian_index.py \
  --account junwin \
  --vault-path /path/to/your/obsidian/vault \
  --max-files 200
```

The CLI accepts the following (notable) options:

- `--base-path`: Storage root path passed to StoragePaths. Default: `data` (relative to repo root). You can also set it via the LUCY_STORAGE_ROOT environment variable.
- `--storage-namespace`: Namespace (subfolder) under the storage root. Default: `data`. Can be overridden with LUCY_STORAGE_NAMESPACE.
- `--account`: Account name to attach to created DocumentRef records. Defaults to your current user (or LUCY_ACCOUNT env var if set).
- `--vault-path`: Path to the vault or folder to index. Can be absolute or relative to the repo root. Default: `<repo-root>/docs/minidoc`.
- `--max-files`: Optional cap on files to index (useful for testing).

### Notes / gotchas

- `--vault-path` can be the vault root or any subfolder.
- The importer indexes all `**/*.md` under that path.
- `--max-files` is optional and is useful for testing.

## Storage location

The CLI respects `--base-path` and the `LUCY_STORAGE_ROOT` environment variable instead of hard-coding absolute paths like `/home/junwin/lucy_storage`.

By default it will write into `<repo-root>/data/data/...` unless you override the base-path/namespace.

## Example YAML frontmatter for tags

```yaml
---
tags:
  - Agent
  - src.agent
---
```

Or:

```yaml
---
tags: Agent
---
```
