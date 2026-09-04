# Runbook: update the Mint NUC Lucy deployment to `develop` with galet pinned `@release/0.1.1`

Purpose: take the Lucy deployment on the Mint NUC from `aug_token_management`
(`73a95c2`) to `develop`, with `galet` pinned to `release/0.1.1` (the
`requirements.txt` change this doc ships with), sqlite-vec available as an
OS-level extension, and the config switched to
`embedding_store_backend=sqlite_vec` + `chat2_store_backend=sqlite` while the
service keeps binding `host 0.0.0.0`.

This document is executed **on the Mint NUC** (or over ssh into it), never on
the Pi. Every phase below is a self-contained `bash` block. Run them in order,
one at a time. Each block is idempotent where possible and stops on first
error (`set -euo pipefail`). Any failure after a change has been applied goes
to Phase 9 (rollback) — rollback is only as good as the Phase 1 backup.

## Target facts and assumptions

| Fact | Value | Status |
|---|---|---|
| Host | Intel NUC, Linux Mint 22.3, python3.12 | from discovery |
| ssh | available | host alias/ip: `[TODO: operator - ssh alias or user@ip, used as `ssh "$MINT"`]` |
| Repo on host | `/home/junwin/src/repos/lucy` | from discovery |
| systemd unit | `lucy.service` | from discovery |
| Current branch / commit | `aug_token_management` @ `73a95c2` | from discovery; `73a95c2` verified ancestor of `develop` in repo history |
| Interpreter used by the service | unknown until `systemctl cat lucy.service` is read (Phase 1) | `[TODO: operator]` |
| Mint config.json local edits | assumed to be host binding / storage paths only; develop's `config.json` differs from `73a95c2`'s only by adding `tasklists.run_ttl_days` (verified) | assumption |
| Whether Mint has a `config.local.json` override | unknown | detected automatically in Phase 5 |
| Mint storage root / namespace | unknown until read from merged config (Phase 1) | `[TODO: operator]` |

Conventions:
- `sudo -n` everywhere (non-interactive). If sudo prompts for a password the
  block fails fast — arrange passwordless sudo for the ssh user first
  `[TODO: operator]`.
- Run each phase as a single `bash` block, e.g. over ssh:
  `ssh "$MINT" 'bash -s' <<'PHASE' ... PHASE` (paste the block between the
  markers). Do not paste phases into a `python`/`bash` REPL.
- `BACKUP` is recorded in `$HOME/.lucy-update-backup` by Phase 1 and re-read by
  later phases, so phases stay runnable independently.
- `[TODO: ...]` marks the only places where a human decision/input is needed.
  Everything else is deterministic.

---

## Phase 1 — Preflight & backups

Single responsibility: record the before-state and copy everything rollback
needs. Abort if anything here fails.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
SERVICE=lucy

TS=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/lucy-backups/update-$TS"
mkdir -p "$BACKUP/storage"
echo "$BACKUP" > "$HOME/.lucy-update-backup"

echo "== 1.1 service unit (derive the interpreter PY from ExecStart) =="
systemctl cat "$SERVICE.service" | grep -E "^(ExecStart|WorkingDirectory|User|Environment)=" || true
# [TODO: operator] Set PY below from ExecStart's first token (e.g. /home/junwin/src/repos/lucy/venv/bin/python).
# If ExecStart is a wrapper script, open it and find the python it calls. PY must be the
# interpreter the service actually runs - everything in phases 3/6/8 must use it.
PY=/home/junwin/src/repos/lucy/venv/bin/python
"$PY" -V   # must report Python 3.12 on the Mint; if the path is wrong the block stops here

echo "== 1.2 current git state =="
git -C "$LUCY_HOME" rev-parse HEAD          | tee "$BACKUP/commit-before.txt"   # expect 73a95c2
git -C "$LUCY_HOME" branch --show-current   | tee "$BACKUP/branch-before.txt"   # expect aug_token_management
git -C "$LUCY_HOME" status --porcelain      | tee "$BACKUP/tree-before.txt"

echo "== 1.3 config backups =="
cp -a "$LUCY_HOME/config.json" "$BACKUP/config.json"
if [ -f "$LUCY_HOME/config.local.json" ]; then cp -a "$LUCY_HOME/config.local.json" "$BACKUP/config.local.json"; fi

echo "== 1.4 resolve storage root / namespace from the merged config =="
cd "$LUCY_HOME"
python3 - <<'PY'
from src.config_manager import ConfigManager
c = ConfigManager("config.json")
for k in ("storage_root_path", "storage_namespace", "embedding_store_backend",
          "chat2_store_backend", "host", "port"):
    print(f"{k}={c.get(k)!r}")
PY
# Expect: host='0.0.0.0', backend keys unset or 'jsonl'. storage_root_path MUST be a Linux
# path on the Mint. If it prints the committed placeholder 'C:/Users/...', STOP:
# the Mint's real storage path lives in local edits/config.local.json that this runbook
# assumed would surface here. [TODO: operator - reconcile before continuing]

echo "== 1.5 backup sqlite storage files under the storage root =="
# Fill SR/NS from the 1.4 output. Example: SR=/home/junwin/lucydata, NS=data
SR=/home/junwin/lucydata    # [TODO: operator - set from 1.4]
NS=data                     # [TODO: operator - set from 1.4]
cd "$SR"
find "$NS" -maxdepth 3 \( -name "*.sqlite" -o -name "*.sqlite-shm" -o -name "*.sqlite-wal" \) -print | while read -r f; do
  mkdir -p "$BACKUP/storage/$(dirname "$f")"
  cp -a "$f" "$BACKUP/storage/$f"
done
echo "backup dir: $BACKUP"
```

Abort if: the expected branch/commit (1.2) differs, `config.json` is missing,
or `storage_root_path` is not a Linux path (1.4). Continue only after
reconciling `[TODO]` items.

---

## Phase 2 — Checkout `develop` + pull

Single responsibility: move the repo to the remote `develop` head with a clean
tracked tree. `config.json` is a tracked file; the Mint's local edits to it
were backed up in Phase 1 and are re-applied in Phase 5 — nothing is lost.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
BACKUP=$(cat "$HOME/.lucy-update-backup")

cd "$LUCY_HOME"

# 2.1 refuse to auto-discard anything except config.json
DIRTY=$(git status --porcelain | grep -v '^??' | grep -v ' config.json$' || true)
if [ -n "$DIRTY" ]; then
  echo "ABORT: unexpected dirty tracked files - resolve or back up first:"
  echo "$DIRTY"
  exit 1
fi

git fetch origin develop
git checkout -- config.json     # discard Mint-local edits to the tracked file (backed up in 1.3)
git checkout develop
git pull --ff-only origin develop

# 2.2 post-conditions
echo "branch: $(git rev-parse --abbrev-ref HEAD)"    # must print develop
echo "head:   $(git rev-parse HEAD)"
grep -n "galet" requirements.txt
# The last line MUST contain '@release/0.1.1'. If it is still the unpinned
# '#egg=galet' form, the pin is not merged upstream yet - STOP here and do not
# run Phase 3. [TODO: operator - confirm the requirements.txt change is on origin/develop]
```

Abort if: 2.1 finds dirty files, or the galet line in `requirements.txt` is
not pinned to `@release/0.1.1`.

---

## Phase 3 — venv update (galet pinned `@release/0.1.1`)

Single responsibility: make the service interpreter's environment match the
new `requirements.txt`.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
PY=/home/junwin/src/repos/lucy/venv/bin/python    # [TODO: operator - same PY as Phase 1.1]

cd "$LUCY_HOME"
"$PY" -m pip install -r requirements.txt

# verify: galet importable, and its editable checkout sits at the release/0.1.1 commit
"$PY" -c "import galet; print('galet OK:', galet.__file__)"
LOC=$("$PY" -m pip show galet | awk '/^Location:/{print $2}')
echo "galet checkout location: $LOC/galet"
git -C "$LOC/galet" log -1 --oneline
git -C "$LOC/galet" describe --tags --always 2>/dev/null || true
# Expect the checkout to be the release/0.1.1 commit/tag. [TODO: operator - eyeball the two lines above]
```

Abort if: pip fails, or `import galet` fails (network to github.com is needed
for the `-e git+https://...@release/0.1.1` install).

Note: if the Mint has no venv yet (Phase 1.1 shows the service running on a
bare interpreter), create one first and point the unit at it
`[TODO: operator]`: `python3.12 -m venv "$LUCY_HOME/venv"` then repeat this
phase.

---

## Phase 4 — sqlite-vec OS install + path verification

Single responsibility: make the compiled `vec0.so` exist at the **exact path
the code loads**. The code constant (verified in
`src/storage/vec0_embedding_store.py:13`) is:

```python
DEFAULT_SQLITE_VEC_EXTENSION_PATH = "/usr/local/lib/sqlite-vec/vec0.so"
```

The store calls `sqlite3.Connection.load_extension(...)` with that path at
startup, so the file must exist there (symlink is fine). Verify the constant
on the checked-out code first, then install.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
EXT=/usr/local/lib/sqlite-vec/vec0.so

# 4.0 confirm the load path constant in the code we are about to run
grep -n 'DEFAULT_SQLITE_VEC_EXTENSION_PATH = ' "$LUCY_HOME/src/storage/vec0_embedding_store.py"

# 4.1 attempt the packaged install (first attempt; may not exist for Mint 22.3 / py3.12)
sudo -n apt-get update
sudo -n apt-get install -y python3-sqlite-vec || echo "PACKAGE-UNAVAILABLE (continuing to locate/fallback)"

# 4.2 verification: vec0.so at the exact path the code loads
if [ ! -f "$EXT" ]; then
  FOUND=$(dpkg -L python3-sqlite-vec 2>/dev/null | grep -E 'vec0\.so$' | head -1 || true)
  if [ -z "$FOUND" ]; then
    FOUND=$(find /usr/lib/python3 /usr/local/lib/python3.12 /usr/lib -name 'vec0.so' 2>/dev/null | head -1 || true)
  fi
  if [ -n "$FOUND" ]; then
    echo "linking $FOUND -> $EXT"
    sudo -n mkdir -p /usr/local/lib/sqlite-vec
    sudo -n ln -sf "$FOUND" "$EXT"
  else
    echo "MANUAL-FALLBACK-REQUIRED - see note below; do not continue to Phase 5 until $EXT exists"
    exit 1
  fi
fi
sudo -n test -f "$EXT" && echo "OK: vec0.so present at $EXT"

# 4.3 functional check: load it with the exact path and ask for its version
python3 - <<'PY'
import sqlite3
c = sqlite3.connect(":memory:")
c.enable_load_extension(True)
c.load_extension("/usr/local/lib/sqlite-vec/vec0.so")
print("vec_version:", c.execute("select vec_version()").fetchone()[0])
PY
```

Manual fallback (only when 4.2 prints `MANUAL-FALLBACK-REQUIRED`):
`python3-sqlite-vec` is not in the Mint 22.3 repos, or ships no loadable
`.so`. The NUC is Intel (`x86_64`) — never fetch an `aarch64` build.
- Option A: `sudo -n "$PY" -m pip install sqlite-vec`, then find the `vec0.so`
  inside the installed package and symlink it to `$EXT` (repeat 4.2/4.3).
- Option B: download the prebuilt loadable extension for linux `x86_64` from
  the sqlite-vec GitHub releases page
  (https://github.com/asg017/sqlite-vec/releases), unzip `vec0.so` into
  `/usr/local/lib/sqlite-vec/` `[TODO: operator - pick the release version]`,
  then repeat 4.2/4.3.

Abort if: 4.2 or 4.3 fails — the service will crash at startup with a
`load_extension` error otherwise.

---

## Phase 5 — Config keys (keep `host 0.0.0.0`, add the two backends)

Single responsibility: end with the merged config that the app will actually
see having `host='0.0.0.0'`, `embedding_store_backend='sqlite_vec'`,
`chat2_store_backend='sqlite'`, plus every Mint-local value that existed
before the update.

How the config loads (verified in `src/config_manager.py`):
`ConfigManager("config.json")` deep-merges `config.local.json` on top of
`config.json` when the local file exists — local keys win. So the edit target
is `config.local.json` if the Mint has one, otherwise the tracked `config.json`
(which is where the task's discovery says the Mint's `host 0.0.0.0` lives).

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
BACKUP=$(cat "$HOME/.lucy-update-backup")

cd "$LUCY_HOME"
TARGET=config.json
[ -f config.local.json ] && TARGET=config.local.json
echo "editing: $TARGET"

python3 - "$BACKUP" "$TARGET" <<'PY'
import json, sys
backup, target = sys.argv[1], sys.argv[2]

new = json.load(open(target))
if target == "config.json":
    # Tracked file: carry Mint-local overrides from the pre-update backup over the
    # fresh develop version, then force the three required values.
    # Safe because the only config.json change 73a95c2..develop is +tasklists (verified).
    old = json.load(open(backup + "/config.json"))
    merged = dict(new)
    for k, v in old.items():
        if k not in merged:
            merged[k] = v
        elif isinstance(v, dict) and isinstance(merged[k], dict):
            for kk, vv in v.items():
                merged[k].setdefault(kk, vv)
else:
    # config.local.json is untracked and was untouched by Phase 2; just add keys.
    merged = new

merged["host"] = "0.0.0.0"                     # keep LAN binding (task requirement)
merged["embedding_store_backend"] = "sqlite_vec"
merged["chat2_store_backend"] = "sqlite"
with open(target, "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")
print("wrote", target)
PY

# 5.2 verify the merged view the app will see
python3 - <<'PY'
from src.config_manager import ConfigManager
c = ConfigManager("config.json")
for k in ("host", "port", "embedding_store_backend", "chat2_store_backend",
          "storage_root_path", "storage_namespace"):
    print(f"{k}={c.get(k)!r}")
PY
# MUST print: host='0.0.0.0', embedding_store_backend='sqlite_vec',
#             chat2_store_backend='sqlite', storage_root_path=<Linux path>.
# If TARGET was config.json, `git diff config.json` should now show the local
# values restored plus exactly those three key changes. Compare the final file
# against "$BACKUP/config.json" to confirm no key was dropped.
```

Abort if: 5.2 shows anything other than the expected values, or
`storage_root_path` is the `C:/Users/...` placeholder.

---

## Phase 6 — Optional data migration to the sqlite stores

Single responsibility (only if you want history carried into the new backends;
skip entirely for a green-field Mint with no stored chats/embeddings): lift
existing records into the sqlite stores the new backends serve. All scripts
are one-time lifts (copy, never prune) and idempotent; re-running overwrites
the same keys. Run with `--dry-run` first.

Migration chain on disk (defaults verified in the scripts and
`src/container_config.py`; all paths resolve from config or `--base-path`):
- chat2 jsonl `<SR>/<NS>/chat2/` -> `scripts/migrate_chat2_to_sqlite.py` -> `<SR>/<NS>/chat2.sqlite`
- embeddings files `<SR>/<NS>/embeddings/` -> `scripts/migrate_embeddings_to_sqlite.py` -> `<SR>/<NS>/embeddings.sqlite` (kv)
- embeddings kv -> vec0 tables (same `embeddings.sqlite`) -> `scripts/migrate_embeddings_to_vec0.py`

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
PY=/home/junwin/src/repos/lucy/venv/bin/python    # [TODO: operator - same PY as Phase 1.1]
SR=/home/junwin/lucydata                          # [TODO: operator - same as Phase 1.5]
NS=data                                           # [TODO: operator - same as Phase 1.5]
ACCOUNT=junwin                                    # [TODO: operator - confirm account name]

cd "$LUCY_HOME"

echo "== 6.1 dry-runs (write nothing) =="
"$PY" scripts/migrate_chat2_to_sqlite.py --config config.json --dry-run --verbose
"$PY" scripts/migrate_embeddings_to_sqlite.py --base-path "$SR" --storage-namespace "$NS" --dry-run --verbose
"$PY" scripts/migrate_embeddings_to_vec0.py  --base-path "$SR" --storage-namespace "$NS" --account "$ACCOUNT" --dry-run --verbose
# A leg reporting 0 records means that source is empty -> skip that leg for real.
# If Mint's current layout differs from the chain above (e.g. embeddings already in a
# sqlite kv store, or never used), start the chain at the matching leg. [TODO: operator]
```

Real runs (only after the dry-runs look right). Recommended with the service
stopped so chat2 jsonl writes cannot land after the copy and before the
backend switch in Phase 7:

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
PY=/home/junwin/src/repos/lucy/venv/bin/python    # [TODO: operator - same PY as Phase 1.1]
SR=/home/junwin/lucydata                          # [TODO: operator - same as Phase 1.5]
NS=data
ACCOUNT=junwin

cd "$LUCY_HOME"
sudo -n systemctl stop lucy
"$PY" scripts/migrate_chat2_to_sqlite.py --config config.json --verbose
"$PY" scripts/migrate_embeddings_to_sqlite.py --base-path "$SR" --storage-namespace "$NS" --verbose
"$PY" scripts/migrate_embeddings_to_vec0.py  --base-path "$SR" --storage-namespace "$NS" --account "$ACCOUNT" --verbose
# do NOT restart here if you skipped stopping the service - Phase 7 restarts anyway
```

Abort if: a dry-run errors (the vec0 script requires `$SR/$NS/embeddings.sqlite`
to already exist and the `$EXT` extension file when not dry-running).

---

## Phase 7 — Service restart and log check

Single responsibility: bring the service up on the new code/config and confirm
it boots cleanly.

```bash
set -euo pipefail
SERVICE=lucy

sudo -n systemctl restart "$SERVICE"
sleep 5

systemctl is-active "$SERVICE"                  # must print: active
systemctl show "$SERVICE" -p ActiveState,SubState,ExecMainPID

sudo -n journalctl -u "$SERVICE" -n 200 --no-pager | grep -iE "traceback|error|vec0|sqlite|ConfigManager|Merged local config" || true
# Read the tail: look for ConfigManager "Merged local config from ..." (expected when
# config.local.json exists) and for any Traceback mentioning vec0 / load_extension /
# sqlite / ValueError (a misconfiguration fails loudly at container build time).
# [TODO: operator - eyeball the journal tail and confirm it ends with the Flask
#  "Running on http://0.0.0.0:<port>" line]
```

Abort if: `is-active` is not `active`, or the journal shows a Traceback. A
`load_extension`/vec0 error means Phase 4 was not satisfied — fix that, then
re-run this phase. Any other Traceback: roll back (Phase 9).

---

## Phase 8 — Verification

Single responsibility: prove the four success criteria — service active, API
reachable, a real `/ask` round-trip works, and the embeddings/vec0 path works.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
PY=/home/junwin/src/repos/lucy/venv/bin/python    # [TODO: operator - same PY as Phase 1.1]
SERVICE=lucy
PORT=$(cd "$LUCY_HOME" && python3 - <<'PY'
from src.config_manager import ConfigManager
print(ConfigManager("config.json").get("port", 5000))
PY
)

echo "== 8.1 service active =="
systemctl is-active "$SERVICE"                    # expect: active
systemctl is-enabled "$SERVICE"                   # expect: enabled (survives reboot)

echo "== 8.2 API reachable =="
curl -fsS -o /dev/null -w "swagger.json HTTP %{http_code}\n" "http://127.0.0.1:$PORT/swagger.json"
curl -fsS "http://127.0.0.1:$PORT/agents" | head -c 400; echo
# Optional LAN check (host is 0.0.0.0): from another machine
#   curl -fsS "http://<mint-ip>:$PORT/swagger.json"   [TODO: operator]

echo "== 8.3 embeddings path: vec0 store round-trip on a throwaway db =="
"$PY" - <<'PY'
import os, tempfile
from src.storage.models import EmbeddingRecord
from src.storage.vec0_embedding_store import Vec0EmbeddingStore, DEFAULT_SQLITE_VEC_EXTENSION_PATH

assert os.path.exists(DEFAULT_SQLITE_VEC_EXTENSION_PATH), DEFAULT_SQLITE_VEC_EXTENSION_PATH
db = os.path.join(tempfile.mkdtemp(), "embeddings.sqlite")
with Vec0EmbeddingStore(db) as s:
    s.upsert_embedding(EmbeddingRecord(
        id="probe-1", namespace="probe", account_name="junwin",
        source_type="test", source_id="probe", vector=[0.0] * 1536))
    hits = s.query_embeddings(["probe"], "junwin", [0.0] * 1536, top_k=1)
    assert len(hits) == 1 and hits[0][0].id == "probe-1", hits
print("vec0 store round-trip OK on", DEFAULT_SQLITE_VEC_EXTENSION_PATH)
PY

echo "== 8.4 ask a test question =="
AGENT=$(curl -fsS "http://127.0.0.1:$PORT/agents" | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('name',''))" 2>/dev/null || true)
# [TODO: operator] if AGENT came back empty, pick an agent name from the /agents
# output above and hard-code it here.
curl -fsS -X POST "http://127.0.0.1:$PORT/ask" \
  -H 'Content-Type: application/json' \
  -d "{\"question\":\"Reply with exactly: PONG\",\"agentName\":\"$AGENT\",\"accountName\":\"junwin\"}" \
  --max-time 120 | head -c 600; echo
# Expect an answer containing PONG. This also proves chat2 sqlite persistence is live
# (the handler writes the session through Chat2Store -> chat2.sqlite).
```

Abort/roll back if: any of 8.1-8.4 fails. 8.4 can take a while (LLM call) —
only treat it as failed on a non-200 or empty/error body, not on slowness.

---

## Phase 9 — Rollback procedure

Single responsibility: return to the exact pre-update state captured in Phase
1. Only run this if a later phase failed and you decided to undo.

```bash
set -euo pipefail
LUCY_HOME=/home/junwin/src/repos/lucy
SERVICE=lucy
PY=/home/junwin/src/repos/lucy/venv/bin/python    # [TODO: operator - same PY as Phase 1.1]
BACKUP=$(cat "$HOME/.lucy-update-backup")

echo "restoring from: $BACKUP"
[ -f "$BACKUP/config.json" ] || { echo "ABORT: backup missing"; exit 1; }

sudo -n systemctl stop "$SERVICE"

cd "$LUCY_HOME"

# 9.1 code back to the pre-update commit (branch aug_token_management @ 73a95c2)
git checkout -- config.json 2>/dev/null || true   # discard Phase 5 edits (backup restored next)
git checkout aug_token_management
git reset --hard 73a95c2
git rev-parse HEAD                                # must print 73a95c2

# 9.2 config back to the exact pre-update files
cp -a "$BACKUP/config.json" config.json
if [ -f "$BACKUP/config.local.json" ]; then
  cp -a "$BACKUP/config.local.json" config.local.json
fi

# 9.3 venv back to the old branch's requirements
# Note: at 73a95c2 requirements.txt pins galet WITHOUT a ref ('-e git+.../#egg=galet'),
# so this reinstalls galet from its default branch HEAD - not the exact old build.
# [TODO: operator] if bit-exact venv restore matters, reinstall from the original
# galet commit instead of re-running pip here.
"$PY" -m pip install -r requirements.txt

# 9.4 sqlite-vec stays installed (harmless for the old backend). Optional strict
# removal: sudo -n apt-get remove -y python3-sqlite-vec   # [TODO: operator - only if desired]

sudo -n systemctl start "$SERVICE"
sleep 5
systemctl is-active "$SERVICE"                    # must print: active

# 9.5 verify old behavior: config backends unset/jsonl, host still 0.0.0.0
cd "$LUCY_HOME" && python3 - <<'PY'
from src.config_manager import ConfigManager
c = ConfigManager("config.json")
print("host=", c.get("host"), "embedding_store_backend=", c.get("embedding_store_backend"),
      "chat2_store_backend=", c.get("chat2_store_backend"))
PY
sudo -n journalctl -u "$SERVICE" -n 100 --no-pager | grep -iE "traceback|error" || true
echo "rollback complete - re-run Phase 8 checks against the old deployment if needed"
```

Abort if: `git rev-parse HEAD` is not `73a95c2`, or the service does not come
back `active`. If rollback itself fails, stop and call for help — do not touch
any other file or host.

---

## Facts encoded in this runbook (with where they were verified)

- `73a95c2` (aug_token_management) is an ancestor of `develop` — verified via
  `git merge-base --is-ancestor` in the repo.
- `config.json` is a tracked file; `73a95c2..develop` changes it only by adding
  `tasklists.run_ttl_days` (verified via `git diff 73a95c2 develop -- config.json`).
- `config.local.json` (gitignored) is deep-merged over `config.json` and wins —
  `src/config_manager.py` (`load_config`, `_deep_merge`).
- sqlite-vec load path constant: `DEFAULT_SQLITE_VEC_EXTENSION_PATH =
  "/usr/local/lib/sqlite-vec/vec0.so"` — `src/storage/vec0_embedding_store.py:13`;
  loaded via `sqlite3.Connection.load_extension` in `Vec0EmbeddingStore.__init__`.
  Config override key `sqlite_vec_extension_path` exists but the canonical path
  above is what this runbook guarantees.
- Backend keys and db-path defaults — `src/container_config.py`:
  `embedding_store_backend` `file|sqlite|sqlite_vec`, `chat2_store_backend`
  `jsonl|sqlite`; `embedding_store_db_path`/`chat2_store_db_path` default to
  `<storage_root>/<namespace>/embeddings.sqlite` and `chat2.sqlite`; storage
  root defaults to `/home/junwin/lucydata` when unset.
- Flask bind: `app.py` runs with `host=config.get("host", "0.0.0.0")`,
  `port=config.get("port", 5000)`. Routes used for verification:
  `GET /swagger.json`, `GET /agents`, `POST /ask` (payload keys `question`,
  `agentName`, `accountName` — `src/message_endpoints/ask_request_handler.py`).
- Migration scripts under `scripts/`: `migrate_chat2_to_sqlite.py`
  (jsonl -> chat2.sqlite), `migrate_embeddings_to_sqlite.py` (files -> kv),
  `migrate_embeddings_to_vec0.py` (kv -> vec0 tables; needs the extension file
  present and the service venv because it imports galet transitively).
