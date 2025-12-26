import os
from pathlib import Path

from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import DocumentRef


def test_search_documents_poor_man_basic(tmp_path):
    base = tmp_path / "data"
    store = JsonFileStorage(str(base))

    # Create some documents for a single account
    docs = [
        DocumentRef(
            id="doc1",
            account_name="alice",
            path="/docs/project_plan.md",
            kind="note",
            title="Project Plan",
            tags=["project", "planning"],
            metadata={"description": "High level project plan"},
        ),
        DocumentRef(
            id="doc2",
            account_name="alice",
            path="/docs/meeting_notes.md",
            kind="note",
            title="Meeting Notes",
            tags=["meeting"],
            metadata={"description": "Notes from project kickoff meeting"},
        ),
        DocumentRef(
            id="doc3",
            account_name="alice",
            path="/docs/random.md",
            kind="note",
            title="Random Thoughts",
            tags=["misc"],
            metadata={"description": "Unrelated musings"},
        ),
    ]

    for d in docs:
        store.upsert_document(d)

    # Query that should match project-related docs more strongly
    results = store.search_documents_poor_man(
        account_name="alice",
        query="project plan",
        kind="note",
        limit=10,
    )

    # We expect at least doc1 and doc2 to appear, with doc1 first
    ids = [d.id for d in results]

    assert "doc1" in ids
    assert "doc2" in ids
    assert ids.index("doc1") < ids.index("doc2")

    # A query that should only match the random doc
    results_random = store.search_documents_poor_man(
        account_name="alice",
        query="unrelated musings",
        kind="note",
        limit=10,
    )

    ids_random = [d.id for d in results_random]
    assert ids_random[0] == "doc3"


def test_search_documents_poor_man_empty_query_returns_limited_list(tmp_path):
    base = tmp_path / "data"
    store = JsonFileStorage(str(base))

    for i in range(5):
        store.upsert_document(
            DocumentRef(
                id=f"doc{i}",
                account_name="bob",
                path=f"/docs/{i}.md",
                kind="note",
                title=f"Doc {i}",
                tags=[],
                metadata={},
            )
        )

    results = store.search_documents_poor_man(
        account_name="bob",
        query="   ",  # empty/whitespace query
        kind="note",
        limit=3,
    )

    assert len(results) == 3
