# ==============================================================================
# FILE 4: tests/storage/test_storage_contexts.py
# ==============================================================================

import pytest
from datetime import datetime
from src.storage.models import ContextState


class TestContexts:
    """Test context/whiteboard operations."""
    
    def test_save_and_load_context(self, storage):
        """Test saving and loading context state."""
        context = ContextState(
            id="therapy_session_001",
            account_name="junwin",
            data={
                "goal": "retirement planning",
                "facts": ["retired 2023", "moved to Evanston"],
                "mood": "reflective",
            },
            updated_at=datetime.utcnow(),
        )
        
        storage.save_context(context)
        
        retrieved = storage.get_context("junwin", "therapy_session_001")
        assert retrieved is not None
        assert retrieved.id == "therapy_session_001"
        assert retrieved.data["goal"] == "retirement planning"
        assert "retired 2023" in retrieved.data["facts"]
    
    def test_update_context(self, storage):
        """Test updating existing context."""
        context = ContextState(
            id="ctx_001",
            account_name="junwin",
            data={"count": 1},
            updated_at=datetime.utcnow(),
        )
        storage.save_context(context)
        
        context.data["count"] = 2
        context.data["new_field"] = "value"
        context.updated_at = datetime.utcnow()
        storage.save_context(context)
        
        retrieved = storage.get_context("junwin", "ctx_001")
        assert retrieved.data["count"] == 2
        assert retrieved.data["new_field"] == "value"
    
    def test_get_nonexistent_context(self, storage):
        """Test retrieving a context that doesn't exist."""
        result = storage.get_context("junwin", "nonexistent")
        assert result is None