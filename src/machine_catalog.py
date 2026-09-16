"""Validated machine definitions and loader."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


class MachineConfigError(ValueError):
    pass


def _text(value: Any, label: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise MachineConfigError(f"{label} must be a string")
    value = value.strip()
    if required and not value:
        raise MachineConfigError(f"{label} is required")
    return value


def _items(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise MachineConfigError(f"{label} must be a list")
    result = tuple(_text(item, label, True) for item in value)
    if len(result) != len(set(result)):
        raise MachineConfigError(f"{label} contains duplicates")
    return result


@dataclass(frozen=True)
class MachineDefinition:
    name: str
    host: str
    enabled: bool = True
    scheme: str = "http"
    port: int = 5000
    auth_profile: Optional[str] = None
    api_key: str = field(default="", repr=False, compare=False)
    session_id: str = ""
    default_agent: str = ""
    default_context: str = ""
    agents: tuple[str, ...] = ()
    capabilities: frozenset[str] = field(default_factory=frozenset)
    projects: Mapping[str, str] = field(default_factory=dict)
    model_sources: tuple[str, ...] = ()
    models: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any], *, strict: bool = True):
        if not isinstance(data, Mapping):
            raise MachineConfigError(f"machine {name!r} must be an object")
        allowed = {"enabled", "scheme", "host", "port", "auth_profile", "api_key",
                   "session_id", "default_agent", "default_context", "agents",
                   "capabilities", "projects", "model_sources", "models"}
        unknown = set(data) - allowed
        if strict and unknown:
            raise MachineConfigError(f"machine {name!r} contains unknown fields: " + ", ".join(sorted(unknown)))
        host = _text(data.get("host"), f"machine {name!r} host", True)
        if "://" in host:
            raise MachineConfigError(f"machine {name!r} host must not include a URL scheme")
        scheme = _text(data.get("scheme", "http"), f"machine {name!r} scheme", True).lower().rstrip(":/")
        if scheme not in {"http", "https"}:
            raise MachineConfigError(f"machine {name!r} scheme must be http or https")
        port = data.get("port", 5000)
        if isinstance(port, bool):
            raise MachineConfigError(f"machine {name!r} port must be an integer")
        try:
            port = int(port)
        except (TypeError, ValueError) as exc:
            raise MachineConfigError(f"machine {name!r} port must be an integer") from exc
        if not 1 <= port <= 65535:
            raise MachineConfigError(f"machine {name!r} port must be between 1 and 65535")
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise MachineConfigError(f"machine {name!r} enabled must be a bool")
        agents = _items(data.get("agents", ()), f"machine {name!r} agents")
        default_agent = _text(data.get("default_agent"), f"machine {name!r} default_agent")
        if agents and default_agent and default_agent not in agents:
            raise MachineConfigError(f"machine {name!r} default_agent is not listed in agents")
        raw_projects = data.get("projects", {})
        if not isinstance(raw_projects, Mapping):
            raise MachineConfigError(f"machine {name!r} projects must be an object")
        projects = {_text(k, "project name", True): _text(v, "project path", True) for k, v in raw_projects.items()}
        auth_profile = _text(data.get("auth_profile"), "auth_profile") or None
        return cls(
            name=_text(name, "machine name", True), host=host, enabled=enabled,
            scheme=scheme, port=port, auth_profile=auth_profile,
            api_key=_text(data.get("api_key"), "api_key"),
            session_id=_text(data.get("session_id"), "session_id"),
            default_agent=default_agent,
            default_context=_text(data.get("default_context"), "default_context"),
            agents=agents,
            capabilities=frozenset(_items(data.get("capabilities", ()), f"machine {name!r} capabilities")),
            projects=projects,
            model_sources=_items(data.get("model_sources", ()), f"machine {name!r} model_sources"),
            models=_items(data.get("models", ()), f"machine {name!r} models"),
        )

    @property
    def ask_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}/ask"

    def session_id_for(self, agent: str) -> str:
        """Return a stable session ID scoped to this machine and agent."""

        base = self.session_id or f"delegate-{self.name}"
        agent_name = agent.strip()
        return f"{base}-{agent_name}" if agent_name else base

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def provides_agent(self, agent: str) -> bool:
        return not self.agents or agent in self.agents

    def provides_model(self, source: str, model: str) -> bool:
        return (not self.model_sources or source in self.model_sources) and (not self.models or model in self.models)

    def project_path(self, project: str) -> Optional[str]:
        return self.projects.get(project)


class MachineManager:
    def __init__(self, path: str, *, strict: bool = True):
        self.path, self.strict = Path(path), strict
        self._machines: dict[str, MachineDefinition] = {}

    @classmethod
    def beside_config(cls, config_file: str, *, machines_path: Optional[str] = None, strict: bool = True):
        path = Path(machines_path) if machines_path else Path(config_file).resolve().parent / "config.local.machines.json"
        return cls(str(path), strict=strict)

    def load(self) -> dict[str, MachineDefinition]:
        if not self.path.exists():
            self._machines = {}
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MachineConfigError(f"invalid machines config {self.path}: {exc}") from exc
        raw = data.get("machines", {}) if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            raise MachineConfigError("machines must be an object")
        self._machines = {name: MachineDefinition.from_dict(name, value, strict=self.strict) for name, value in raw.items()}
        return dict(self._machines)

    def machines(self, *, enabled_only: bool = False) -> tuple[MachineDefinition, ...]:
        values = (m for m in self._machines.values() if m.enabled or not enabled_only)
        return tuple(sorted(values, key=lambda m: m.name))

    def get(self, name: str, *, require_enabled: bool = False) -> Optional[MachineDefinition]:
        value = self._machines.get(name)
        return value if value and (value.enabled or not require_enabled) else None

    def eligible(self, *, agent=None, capability=None, source=None, model=None, project=None):
        return tuple(m for m in self.machines(enabled_only=True)
                     if (not agent or m.provides_agent(agent))
                     and (not capability or m.supports(capability))
                     and (not source or not model or m.provides_model(source, model))
                     and (not project or m.project_path(project) is not None))
