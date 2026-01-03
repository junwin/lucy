import os
import sys

import pytest


# Ensure repo root is on sys.path so `import src...` works in tests.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture()
def storage(tmp_path):
    """JsonFileStorage instance rooted in a temp directory for isolation."""
    from src.storage.json_file_storage import JsonFileStorage

    return JsonFileStorage(base_path=str(tmp_path))
