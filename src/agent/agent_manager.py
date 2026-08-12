import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from .agent import Agent

logger = logging.getLogger(__name__)


class AgentManager:
    """Manage loading, saving, and accessing Agent definitions.

    Agents are stored as a JSON array in the file configured by agents_path,
    e.g. /home/junwin/src/repos/lucy/static/data/agents.json
    """

    def __init__(self, path: str = "./agents.json", strict_fields: bool = True):
        self.path = Path(path)
        self.strict_fields = strict_fields
        self.agents: List[Agent] = []
        self.load_agents()

    def get_agent(self, name: str) -> Optional[Agent]:
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def is_valid(self, name: str) -> bool:
        return any(agent.name == name for agent in self.agents)

    def load_agents(self, strict: Optional[bool] = None) -> None:
        """Load agents from the configured JSON file.

        Loading is robust: the file must parse as JSON, but individual agent
        configurations are validated on a per-item basis. A single malformed
        agent entry will not prevent other agents from loading.

        Args:
            strict: If provided, overrides self.strict_fields for this load.
                    True = unknown fields raise ValueError (hard-fail per agent).
                    False = unknown fields log a warning and are ignored.
                    When None (default), uses self.strict_fields.
        """
        use_strict = strict if strict is not None else self.strict_fields

        try:
            if not self.path.exists():
                logger.info("Agents file does not exist at %s; starting with empty agent list", self.path)
                self.agents = []
                return

            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)

            # Expect a list of agent dicts; be tolerant of a single dict (wrap it)
            if isinstance(raw, dict):
                logger.warning("Agents file %s contains a JSON object; expected a list. Attempting to load single agent.", self.path)
                raw_agents = [raw]
            elif isinstance(raw, list):
                raw_agents = raw
            else:
                logger.error("Unexpected JSON structure in %s: expected list or object, got %s", self.path, type(raw))
                self.agents = []
                return

            loaded_agents: List[Agent] = []
            for idx, a in enumerate(raw_agents):
                try:
                    agent = Agent.from_dict(a, strict=use_strict)
                    loaded_agents.append(agent)
                except Exception as e:
                    # Log and continue with other agents
                    logger.exception("Failed to load agent at index %d from %s: %s", idx, self.path, e)

            self.agents = loaded_agents
            logger.info("Loaded %d agent(s) from %s", len(self.agents), self.path)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in agents file %s: %s", self.path, e)
            self.agents = []
        except Exception as e:
            logger.exception("Error loading agents from %s: %s", self.path, e)
            self.agents = []

    def save_agents(self) -> None:
        data = [agent.to_dict() for agent in self.agents]
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Saved %d agent(s) to %s", len(self.agents), self.path)
        except Exception:
            logger.exception("Failed to save agents to %s", self.path)

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

    def remove_agent(self, name: str) -> bool:
        """Remove an agent by name (does not auto-save).

        Returns True if an agent was removed, False if no agent matched.
        """
        for idx, existing in enumerate(self.agents):
            if existing.name == name:
                self.agents.pop(idx)
                return True
        return False
