---
tags:
  - scripts
  - lucyproject
  - cli-tools
---

# Scripts

Standalone CLI tools in `scripts/`. Each is a self-contained entrypoint — run with `python scripts/<name>.py`.

## Chat / Curation

| Script | Purpose | Key Flags |
|---|---|---|
| `curate_chats.py` | Curate chat sessions (filter, summarize, archive). Uses `CurationEngine` from `src/curation/core.py`. | `--session-id`, `--account`, `--mode` (filter/summarize/archive), `--preview`, `--publish` |
| `extract_prompt_corpus.py` | Extract prompts from chat sessions into a JSON corpus for evaluation. | `--account`, `--output`, `--limit` |
| `mark_excluded_prompts.py` | Mark prompts for exclusion from eval corpus based on rules. | `--corpus`, `--rules` |
| `dedup_corpus.py` | Deduplicate prompt corpus by first N chars of prompt text. Groups by prefix, keeps first in each group. | `--dry-run`, `--stats`, `--list-groups`, `--prefix-len` (default 256) |

## Document Enrichment

| Script | Purpose | Key Flags |
|---|---|---|
| `eval_enrichment.py` | Evaluate document enrichment quality against prompt corpus. Scores enrichment coverage. | `--corpus`, `--model`, `--limit` |

## Obsidian / Documents

| Script | Purpose | Key Flags |
|---|---|---|
| `obsidian_index.py` | Index an Obsidian vault (or any `.md` folder) into Lucy's document store as `DocumentRef` records. | `--account`, `--vault-path`, `--max-files`, `--base-path`, `--storage-namespace` |
| `migrate_contexts_json_to_md.py` | Convert legacy JSON context files to Markdown format. | (positional args for paths) |

## Meshtastic / Radio

| Script | Purpose | Key Flags |
|---|---|---|
| `check_channels.py` | Check channel configurations on T-Deck Meshtastic devices via serial. Uses `meshtastic` library. | Device port |
| `check_nodedb.py` | Check node database for specific nodes. | Node ID |
| `fix_jutx.py` | Fix configuration for a specific Meshtastic node. | Node ID |
| `msg_pix.py` | Send text messages to a Meshtastic node via serial. | Destination ID, message |
| `query_pix.py` | Query node information and optionally send messages. | Destination ID |
| `read_meshtastic_msgs.py` | Read incoming messages from a connected Meshtastic device. | Port |

## Tests / Ad-hoc

| Script | Purpose | Key Flags |
|---|---|---|
| `test_doc_context.py` | Test document context retrieval — queries embedding search for a given prompt. | Prompt text |
| `test_embeddings.py` | Compare a source string against test strings using embedding similarity. | `--source`, `--tests`, `--tests-file`, `--model`, `--metric`, `--raw` |
| `test_keywords.py` | Test keyword extraction from a query string. | Query text |
| `test_prompt_builder.py` | Test the prompt builder endpoint (HTTP POST to `/ask`). | Prompt text |
| `run_test_prompt.sh` | Shell wrapper that runs `test_prompt_builder.py` with a preset prompt. | — |

## Dependencies

- **Standard library:** `argparse`, `json`, `logging`, `os`, `sys`, `time`, `collections`, `pathlib`
- **Third-party:** `meshtastic` (radio scripts only)
- **Internal:** `src.chat2`, `src.curation`, `src.llm`, `src.storage`, `src.storage_paths`, `src.utils.document_context`, `src.embeddings`, `src.keywords`, `src.config_manager`
