#!/usr/bin/env python3
"""Quick test for get_document_context() — run from repo root with venv active."""

import sys
import json
import logging

logging.basicConfig(level=logging.DEBUG)

# Ensure src is importable
sys.path.insert(0, ".")

from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from src.utils.document_context import get_document_context

# Use the same config as the running app
storage_paths = StoragePaths(
    storage_root_path="/home/junwin/lucy_storage",
    storage_namespace="data",
)
storage = JsonFileStorage(storage_paths)

query = sys.argv[1] if len(sys.argv) > 1 else "tasklists_manage"

results = get_document_context(
    storage=storage,
    account_name="junwin",
    query=query,
    limit=5,
    max_chars=2000,
)

print(f"\n=== Results for query: {query!r} ===")
print(f"Found {len(results)} documents\n")

for i, doc in enumerate(results, 1):
    print(f"--- Result {i} ---")
    print(f"  ID:    {doc['id']}")
    print(f"  Title: {doc['title']}")
    print(f"  Path:  {doc['path']}")
    print(f"  Tags:  {doc['tags']}")
    print(f"  Snippet ({len(doc['snippet'])} chars):")
    print(f"  {doc['snippet'][:500]}")
    print(f"  Truncated: {doc['truncated']}")
    print()
