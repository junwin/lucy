import json
from pathlib import Path
from typing import List, Dict, Optional

from .agent import Agent


class AgentManager:
    """Manage loading, saving, and accessing Agent definitions.

    Agents are stored as a JSON array in the file configured by agents_path,
    e.g. /home/junwin/src/repos/lucy/static/data/agents.json
    """

    def __init__(self, path: str = "./agents.json"):
        self.path = Path(path)
        self.agents: List[Agent] = []
        self.load_agents()

    def get_agent(self, name: str) -> Optional[Agent]:
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def is_valid(self, name: str) -> bool:
        return any(agent.name == name for agent in self.agents)

    def load_agents(self) -> None:
        try:
            if not self.path.exists():
                self.agents = []
                return

            with self.path.open("r", encoding="utf-8") as f:
                raw_agents = json.load(f)

            self.agents = [Agent.from_dict(a) for a in raw_agents]
        except Exception as e:
            # For now, keep simple logging; can be wired to app logger later
            print(f"Error loading agents from {self.path}: {e}")
            self.agents = []

    def save_agents(self) -> None:
        data = [agent.to_dict() for agent in self.agents]
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_agent_names(self) -> List[str]:
        return [agent.name for agent in self.agents]

    def get_available_agents(self) -> List[Agent]:
        return self.agents

    def upsert_agent(self, agent: Agent) -> None:
        """Insert or update an agent in memory (does not auto-save)."""
        for idx, existing in enumerate(self.agents):
            if existing.name == agent.name:
                self.agents[idx] = agent
                break
        else:
            self.agents.append(agent)
