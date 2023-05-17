from src.hierarchical_node import HierarchicalNode

class GoalManager:
    def __init__(self):
        self.goals = {}

    def add_goal(self, goal_name, conversation_id, sub_goals=None):
        goal = Goal(goal_name, conversation_id, sub_goals)
        self.goals[goal.id] = goal

    def update_goal(self, goal_id, new_goal:Goal):
        if goal_id in self.goals:
            goal = self.goals[goal_id]
            goal.name = new_goal_name
            if new_sub_goals:
                goal.sub_goals = new_sub_goals

    def remove_goal(self, goal_id):
        if goal_id in self.goals:
            self.goals.pop(goal_id)

    def add_sub_goal(self, goal_id, sub_goal):
        if goal_id in self.goals:
            self.goals[goal_id].add_sub_goal(sub_goal)

    def remove_sub_goal(self, goal_id, sub_goal):
        if goal_id in self.goals:
            self.goals[goal_id].remove_sub_goal(sub_goal)

    def __repr__(self):
        return f"GoalManager(goals={self.goals})"
