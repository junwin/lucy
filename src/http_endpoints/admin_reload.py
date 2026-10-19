"""Validate both runtime reload candidates before changing either manager."""
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)
_reload_lock = Lock()


def reload_config_and_agents(config, agent_manager):
    # Serialize reload requests within this process. This does not rebuild
    # startup-created services or synchronize separate server workers.
    with _reload_lock:
        stage = "config"
        try:
            candidate = config.read_reload_config()
            strict = candidate.get("strict_agent_fields", True)
            stage = "agents"
            path = Path(candidate.get("agents_path", str(agent_manager.path)))
            agents = agent_manager.read_agents(path=path, strict=strict)
        except Exception as exc:
            logger.exception("Runtime reload failed at %s; live state preserved", stage)
            return {
                "config_reloaded": False,
                "error": "Reload failed. Old config and agents preserved.",
                "failed_stage": stage,
                "detail": str(exc),
            }, 500

        old_names = set(agent_manager.get_agent_names())
        names = [agent.name for agent in agents]
        added = sorted(set(names) - old_names)
        removed = sorted(old_names - set(names))
        summary = config.apply_config(candidate)
        agent_manager.path = path
        agent_manager.strict_fields = strict
        agent_manager.agents = agents
        logger.info("Runtime agents reloaded: added=%s removed=%s total=%d",
                    added, removed, len(names))
        return {
            **summary,
            "agents_loaded": len(names),
            "agent_names": names,
            "agents_added": added,
            "agents_removed": removed,
        }, 200
