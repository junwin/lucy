import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_obsidian_index_cli_runs_and_indexes_one_file(tmp_path, monkeypatch):
    # Use a temporary storage root to avoid writing into the repo data directory.
    tmp_storage = tmp_path / "storage"
    tmp_storage.mkdir()

    env = os.environ.copy()
    env["LUCY_STORAGE_ROOT"] = str(tmp_storage)
    env["LUCY_STORAGE_NAMESPACE"] = "test"
    env["LUCY_ACCOUNT"] = "testuser"

    # Run the CLI script targeting the repo's docs/minidoc and limit to 1 file
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "obsidian_index.py"
    assert script.exists(), f"Expected script at {script}"

    proc = subprocess.run(
        [sys.executable, str(script), "--vault-path", "docs/minidoc", "--max-files", "1"],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    # Ensure the process exited successfully
    assert proc.returncode == 0, f"Script failed: stdout={proc.stdout}\nstderr={proc.stderr}"

    # Check expected output
    assert "Indexed" in proc.stdout
    assert "for account testuser" in proc.stdout
