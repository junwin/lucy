import pytest
from datetime import datetime
from typing import List, Dict, Set
from src.goal import Goal
import time

class TestGoal:
    def test_init(self):
        goal = Goal("test_goal", "test_conversation_id")
        assert goal.name == "test_goal"
        assert goal.conversation_id == "test_conversation_id"
        assert isinstance(goal.utc_timestamp, str)
        assert isinstance(goal.id, str)
        assert isinstance(goal.sub_goals, List)
        assert isinstance(goal.tags, List)
        assert goal.state == "none"

    def get_utc_time(self):
        return datetime.utcnow().isoformat() + "Z"
        
    def test_add_sub_goal(self):
        goal = Goal("test_goal", "test_conversation_id")
        sub_goal = Goal("test_sub_goal", "test_conversation_id")
        goal.add_sub_goal(sub_goal)
        assert sub_goal in goal.sub_goals
        
    def test_remove_sub_goal(self):
        goal = Goal("test_goal", "test_conversation_id")
        sub_goal = Goal("test_sub_goal", "test_conversation_id")
        goal.add_sub_goal(sub_goal)
        goal.remove_sub_goal(sub_goal)
        assert sub_goal not in goal.sub_goals
        
    def test_as_dict(self):
        goal = Goal("test_goal", "test_conversation_id")
        goal_dict = goal.as_dict()
        assert goal_dict["name"] == "test_goal"
        assert goal_dict["conversation_id"] == "test_conversation_id"
        assert isinstance(goal_dict["utc_timestamp"], str)
        assert isinstance(goal_dict["id"], str)
        assert isinstance(goal_dict["sub_goals"], List)
        assert isinstance(goal_dict["tags"], List)
        assert goal_dict["state"] == "none"
        
    def test_from_dict(self):
        goal_dict = {
            "name": "test_goal",
            "conversation_id": "test_conversation_id",
            "utc_timestamp": self.get_utc_time(),
            "id": str(time.time()),
            "sub_goals": [],
            "tags": [],
            "state": "none"
        }
        goal = Goal.from_dict(goal_dict)
        assert goal.name == "test_goal"
        assert goal.conversation_id == "test_conversation_id"
        assert isinstance(goal.utc_timestamp, str)
        assert isinstance(goal.id, str)
        assert isinstance(goal.sub_goals, List)
        assert isinstance(goal.tags, List)
        assert goal.state == "none"