#==============================================================================
# FILE 3: tests/storage/test_storage_profiles.py
# ==============================================================================

import pytest
from src.storage.models import UserProfile, AgentProfile


class TestUserProfiles:
    """Test user profile operations."""
    
    def test_create_user_profile(self, storage):
        """Test creating a user profile."""
        profile = UserProfile(
            account_name="junwin",
            full_name="John Winter",
            preferences={
                "language": "en-US",
                "theme": "dark",
            }
        )
        
        storage.upsert_user_profile(profile)
        
        retrieved = storage.get_user_profile("junwin")
        assert retrieved.account_name == "junwin"
        assert retrieved.full_name == "John Winter"
        assert retrieved.preferences["language"] == "en-US"
    
    def test_update_user_profile(self, storage):
        """Test updating an existing user profile."""
        profile = UserProfile(
            account_name="junwin",
            full_name="John",
            preferences={"theme": "light"}
        )
        storage.upsert_user_profile(profile)
        
        updated = UserProfile(
            account_name="junwin",
            full_name="John Winter",
            preferences={"theme": "dark", "language": "en-US"}
        )
        storage.upsert_user_profile(updated)
        
        retrieved = storage.get_user_profile("junwin")
        assert retrieved.full_name == "John Winter"
        assert retrieved.preferences["theme"] == "dark"
        assert retrieved.preferences["language"] == "en-US"
    
    def test_get_nonexistent_user(self, storage):
        """Test retrieving a user that doesn't exist."""
        result = storage.get_user_profile("nonexistent")
        assert result is None


class TestAgentProfiles:
    """Test agent profile operations."""
    
    def test_create_agent_profile(self, storage):
        """Test creating an agent profile."""
        agent = AgentProfile(
            name="lucy",
            model="gpt-4o",
            temperature=0.7,
            message_processor="default",
            config={"max_tokens": 4000},
        )
        
        storage.upsert_agent_profile(agent)
        
        retrieved = storage.get_agent_profile("lucy")
        assert retrieved.name == "lucy"
        assert retrieved.model == "gpt-4o"
        assert retrieved.temperature == 0.7
        assert retrieved.config["max_tokens"] == 4000
    
    def test_update_agent_profile(self, storage):
        """Test updating agent configuration."""
        agent = AgentProfile(
            name="lucy",
            model="gpt-4",
            temperature=0.5,
            message_processor="default",
        )
        storage.upsert_agent_profile(agent)
        
        agent.model = "gpt-4o"
        agent.temperature = 0.8
        storage.upsert_agent_profile(agent)
        
        retrieved = storage.get_agent_profile("lucy")
        assert retrieved.model == "gpt-4o"
        assert retrieved.temperature == 0.8
    
    def test_get_nonexistent_agent(self, storage):
        """Test retrieving an agent that doesn't exist."""
        result = storage.get_agent_profile("nonexistent")
        assert result is None
