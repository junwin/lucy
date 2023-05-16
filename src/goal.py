import json
import datetime
import time
from typing import List, Dict, Set

class Goal:
    def __init__(self, name:str, conversation_id: str, sub_goals=None):
        self.name = name
        self.conversation_id=conversation_id
        self.utc_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        self.id = str(time.time())
        self.sub_goals = sub_goals if sub_goals else []
        self.tags: List[str] = []
        self.state: str = "none"

    def add_sub_goal(self, sub_goal):
        self.sub_goals.append(sub_goal)

    def remove_sub_goal(self, sub_goal):
        self.sub_goals.remove(sub_goal)

    def __repr__(self):
        return f"Goal(name={self.name}, sub_goals={self.sub_goals})"
    
    def as_dict(self) -> Dict[str, any]:
        return {
            "name": self.name,
            "conversation_id": self.conversation_id,
            "utc_timestamp": self.utc_timestamp,
            "id": self.id,
            "tags": self.tags,
            "sub_goals": [sub_goal.as_dict() for sub_goal in self.sub_goals],
            "state": self.state
        }
    
    @classmethod
    def from_dict(cls, goal_dict: Dict[str, any]) -> 'Goal':
        sub_goals = [cls.from_dict(sub_goal_dict) for sub_goal_dict in goal_dict.get("sub_goals", [])]
        goal = cls(
            name=goal_dict["name"],
            conversation_id=goal_dict["conversation_id"],
            sub_goals=sub_goals
        )
        goal.utc_timestamp = goal_dict.get("utc_timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        goal.id = goal_dict.get("id", str(time.time()))
        goal.tags = goal_dict.get("tags", [])
        goal.state = goal_dict.get("state", "none")
        return goal
