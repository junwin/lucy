import os
from typing import Any, Optional


def resolve_effective_cap(
    key: str,
    agent: Optional[Any],
    config: Optional[Any],
    code_default: int,
    *,
    disable_on_non_positive: bool = False,
) -> Optional[int]:
    if key == "prompt_budget_max_tokens":
        env_value = _env_value("PROMPT_BUDGET_MAX_TOKENS")
        if env_value is not None and env_value > 0:
            return env_value

    agent_value = _agent_value(agent, key)
    if agent_value is not None:
        if agent_value > 0:
            return agent_value
        if disable_on_non_positive:
            return None

    config_value = _config_value(config, key)
    if config_value is not None:
        if config_value > 0:
            return config_value
        if disable_on_non_positive:
            return None

    return code_default


def _agent_value(agent: Optional[Any], key: str) -> Optional[int]:
    if agent is None:
        return None
    if isinstance(agent, dict):
        raw = agent.get(key)
    else:
        raw = getattr(agent, key, None)
    return _as_int(raw)


def _config_value(config: Optional[Any], key: str) -> Optional[int]:
    if config is None:
        return None
    try:
        if isinstance(config, dict):
            raw = config.get(key)
        elif hasattr(config, "get"):
            raw = config.get(key)
        else:
            raw = None
    except Exception:
        raw = None
    return _as_int(raw)


def _env_value(name: str) -> Optional[int]:
    return _as_int(os.getenv(name))


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
