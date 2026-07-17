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


def test_obsidian_index_cli_file_flag(tmp_path, monkeypatch):
    """The --file flag indexes a single .md file."""
    tmp_storage = tmp_path / "storage"
    tmp_storage.mkdir()

    # Create a temporary .md file to index
    md_file = tmp_path / "import-me.md"
    md_file.write_text("---\ntags: [cli, test]\n---\n\n# Single file import\n")

    env = os.environ.copy()
    env["LUCY_STORAGE_ROOT"] = str(tmp_storage)
    env["LUCY_STORAGE_NAMESPACE"] = "test"
    env["LUCY_ACCOUNT"] = "testuser"

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "obsidian_index.py"

    proc = subprocess.run(
        [sys.executable, str(script), "--file", str(md_file)],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"Script failed: stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "Indexed" in proc.stdout
    assert "for account testuser" in proc.stdout


def test_obsidian_index_cli_file_flag_dry_run(tmp_path, monkeypatch):
    """--file --dry-run prints resolved paths without indexing."""
    tmp_storage = tmp_path / "storage"
    tmp_storage.mkdir()

    md_file = tmp_path / "dry-run-test.md"
    md_file.write_text("# dry run\n")

    env = os.environ.copy()
    env["LUCY_STORAGE_ROOT"] = str(tmp_storage)
    env["LUCY_STORAGE_NAMESPACE"] = "test"
    env["LUCY_ACCOUNT"] = "testuser"

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "obsidian_index.py"

    proc = subprocess.run(
        [sys.executable, str(script), "--file", str(md_file), "--dry-run"],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"Script failed: stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "DRY RUN" in proc.stdout
    assert str(md_file) in proc.stdout
    assert "Indexed" not in proc.stdout  # no actual indexing on dry-run
