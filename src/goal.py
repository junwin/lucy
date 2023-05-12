import json
from typing import List, Dict, Set

class Goal:
    def __init__(self, name, conversation_id: str, sub_goals=None):
        self.name = name
        self.conversation_id=conversation_id
        self.utc_timestamp = None
        self.id # ticks as a string
        self.keywords: List[str]
        self.sub_goals = sub_goals if sub_goals else []

    def add_sub_goal(self, sub_goal):
        self.sub_goals.append(sub_goal)

    def remove_sub_goal(self, sub_goal):
        self.sub_goals.remove(sub_goal)

    def __repr__(self):
        return f"Goal(name={self.name}, sub_goals={self.sub_goals})"
