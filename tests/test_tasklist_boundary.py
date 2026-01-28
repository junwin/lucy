import json
from pathlib import Path
import shutil

from src.tasklists import get_tasklist, save_tasklist, list_tasklist_ids


def test_tasklist_boundary_roundtrip(tmp_path):
    # backup existing config.json if present
    repo_root = Path('.').resolve()
    cfg = repo_root / 'config.json'
    backup = None
    if cfg.exists():
        backup = repo_root / 'config.json.bak'
        shutil.copy2(cfg, backup)

    try:
        # point storage_root to the tmp_path
        cfg.write_text(json.dumps({'storage_root_path': str(tmp_path)}), encoding='utf-8')

        acct = 'unittest'
        tid = 't1'
        model = {'tasklist': {'schema_version': 1, 'state': 'Created', 'tasks': [{'id': 1, 'title': 'hello'}]}}

        # save
        save_tasklist(acct, tid, model)

        # load
        res = get_tasklist(acct, tid)
        assert res is not None
        assert 'tasklist' in res
        tl = res['tasklist']
        assert tl['schema_version'] == 1
        assert tl['state'] == 'Created'
        assert isinstance(tl['tasks'], list)
        assert tl['tasks'][0]['title'] == 'hello'

        # list ids
        ids = list_tasklist_ids(acct)
        assert tid in ids

    finally:
        # restore config
        if backup and backup.exists():
            shutil.move(str(backup), str(cfg))
        else:
            try:
                cfg.unlink()
            except Exception:
                pass
