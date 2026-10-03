"""Compose procedural storage once for prompts, tools, and context listing."""

from dataclasses import asdict

from galet_memory import FileProceduralMemory, ProceduralLayout

from src.storage_paths.storage_paths import StoragePaths


def build_procedural_memory(config) -> FileProceduralMemory:
    paths = StoragePaths(
        config.get("storage_root_path") or "/home/junwin/lucydata",
        config.get("storage_namespace") or "data",
    )
    options = config.get("procedural_memory", {}) or {}
    if not isinstance(options, dict):
        raise ValueError("procedural_memory must be an object")
    defaults = ProceduralLayout(
        global_contexts="contexts", account_contexts="contexts/{account}",
        project_contexts=None,
        global_skills="skills", account_skills="skills/{account}",
        project_skills=None,
    )
    overrides = options.get("layout", {})
    if not isinstance(overrides, dict):
        raise ValueError("procedural_memory.layout must be an object")
    layout = {**asdict(defaults), **overrides}
    if any(value is not None and not isinstance(value, str) for value in layout.values()):
        raise ValueError("procedural layout paths must be strings or null")
    return FileProceduralMemory(
        options.get("root") or paths.base,
        ProceduralLayout(**layout),
        context_resolution=options.get("context_resolution", "most_specific"),
    )
