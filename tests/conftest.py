# tests/storage/conftest.py
"""
Shared fixtures and configuration for storage tests.
This allows us to test multiple storage backends with the same test suite.
"""

import pytest
from datetime import datetime
from typing import Type
from src.storage.base import Storage
from src.storage.json_file_storage import JsonFileStorage
# from src.storage.sql_storage import SqlStorage  # Future
# from src.storage.postgres_storage import PostgresStorage  # Future


def get_storage_implementations():
    """
    Registry of storage implementations to test.
    Add new backends here as they're implemented.
    """
    return [
        ("json_file", JsonFileStorage),
        # ("sqlite", SqlStorage),  # Uncomment when ready
        # ("postgres", PostgresStorage),  # Uncomment when ready
    ]


@pytest.fixture(params=get_storage_implementations(), ids=lambda x: x[0])
def storage(request, tmp_path):
    """
    Parametrized fixture that runs each test against all storage backends.
    This ensures all implementations conform to the Storage interface.
    """
    backend_name, backend_class = request.param
    
    if backend_name == "json_file":
        return backend_class(base_path=str(tmp_path / "lucy_storage"))
    
    elif backend_name == "sqlite":
        db_path = tmp_path / "lucy_test.db"
        return backend_class(connection_string=f"sqlite:///{db_path}")
    
    elif backend_name == "postgres":
        # Use a test database or docker container
        return backend_class(
            connection_string="postgresql://test:test@localhost:5432/lucy_test"
        )
    
    raise ValueError(f"Unknown backend: {backend_name}")


@pytest.fixture
def single_json_storage(tmp_path):
    """
    For tests that specifically need JsonFileStorage
    (e.g., testing JSON-specific features).
    """
    return JsonFileStorage(base_path=str(tmp_path / "lucy_storage"))
