import json
from typing import List


class AgentManager:

    def __init__(self, path: str = './agents.json'):
        self.path = path
        self.agents = []
        self.load_agents()

    def get_agent(self, name: str) -> dict:
        for agent in self.agents:
            if agent['name'] == name:
                return agent

        return {}

    def is_valid(self, name: str) -> bool:

        for agent in self.agents:
            if agent['name'] == name:
                return True
        return False

    def load_agents(self) -> None:
        try:
            with open(self.path, 'r') as f:
                self.agents = json.load(f)
        except Exception as e:
            print(e)
            self.agents = []

    def save_agents(self) -> None:
        with open(self.path, 'w') as f:
            json.dump(self.agents, f, indent=2)

    def get_agent_names(self) -> List[str]:
        return [agent['name'] for agent in self.agents]

    def get_available_agents(self) -> List[dict]:
        return self.agents
