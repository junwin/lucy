from src.goal import Goal

class GoalManager:
    def __init__(self):
        self.goals = {}

    def add_goal(self, goal_name, sub_goals=None):
        goal = Goal(goal_name, sub_goals)
        self.goals[goal_name] = goal

    def update_goal(self, old_goal_name, new_goal_name, new_sub_goals=None):
        if old_goal_name in self.goals:
            goal = self.goals.pop(old_goal_name)
            goal.name = new_goal_name
            if new_sub_goals:
                goal.sub_goals = new_sub_goals
            self.goals[new_goal_name] = goal

    def remove_goal(self, goal_name):
        if goal_name in self.goals:
            self.goals.pop(goal_name)

    def add_sub_goal(self, goal_name, sub_goal):
        if goal_name in self.goals:
            self.goals[goal_name].add_sub_goal(sub_goal)

    def remove_sub_goal(self, goal_name, sub_goal):
        if goal_name in self.goals:
            self.goals[goal_name].remove_sub_goal(sub_goal)

    def __repr__(self):
        return f"GoalManager(goals={self.goals})"