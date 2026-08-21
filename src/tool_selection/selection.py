from __future__ import annotations
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["suggest_tools"]

_SELECTION_PROMPTS = {
    "minimal": (
        "You are a tool router. Given a user request, choose the MINIMAL set of "
        "tools from the provided menu that are strictly necessary to fulfill the "
        "request. If no tools are needed, return an empty array. Return ONLY a "
        "JSON array of tool names drawn from the menu. Do not include explanation, "
        "code fences, or markdown."
    ),
    "verb_first": (
        "You are a tool router. Map each concrete action the user asks for to the "
        "tool that performs that action. Examples: 'take a look at / read / check "
        "a file' -> file_load; 'write / save / create / design a file or code' -> "
        "file_save; 'run / execute a command' -> execute_command; 'search the "
        "web' -> web_search_handler. Match on the ACTION the tool performs, not "
        "on topic keywords shared between the request and the tool description. "
        "Return ONLY a JSON array of tool names from the menu. Do not include "
        "explanation, code fences, or markdown."
    ),
}

def _one_line_description(td: Dict[str, Any]) -> str:
    desc = (td.get("description") or "").strip()
    if not desc:
        return "(no description)"
    first = re.split(r"(?<=[.!?])\s+", desc)[0]
    return first[:180]

def _build_menu(defs: List[Dict[str, Any]]) -> str:
    lines = []
    for td in defs:
        name = td.get("name") or "?"
        lines.append(f"- {name}: {_one_line_description(td)}")
    return "\n".join(lines)

def _build_selection_messages(menu: str, prompt_text: str, prompt_style: str = "verb_first") -> List[Dict[str, str]]:
    system = _SELECTION_PROMPTS.get(prompt_style, _SELECTION_PROMPTS["verb_first"])
    user = f"TOOLS:\n{menu}\n\nREQUEST:\n{prompt_text}\n\nReturn only a JSON array of tool names."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

def _parse_json_array(text: str) -> List[str]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    text = text.strip("`")

    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass

    inner = text
    m = re.search(r"\[(.*)\]", text, flags=re.DOTALL)
    if m:
        inner = m.group(1)

    arr = re.findall(r'"([^"]+)"', inner)
    if arr:
        return [x.strip() for x in arr if x.strip()]

    arr = re.findall(r"'([^']+)'", inner)
    if arr:
        return [x.strip() for x in arr if x.strip()]

    if m:
        tokens = re.split(r"[,\s]+", inner.strip())
        return [t.strip() for t in tokens if t.strip()]

    if not re.search(r"[,\s]", inner):
        return [inner.strip()] if inner.strip() else []

    return []

def _clamp_to_known(names: List[str], known: List[str]) -> List[str]:
    known_set = set(known)
    picked = {n for n in names if n in known_set}
    return [n for n in known if n in picked]

def suggest_tools(
    prompt_text: str,
    eligible_defs: List[Dict[str, Any]],
    *,
    llm_call: Callable[[List[Dict[str, str]]], str],
    model: str,
    provider: Optional[str],
    prompt_style: str = "verb_first",
) -> Tuple[List[str], Dict[str, Any]]:
    names = [td.get("name") for td in eligible_defs]
    meta: Dict[str, Any] = {
        "prompt_style": prompt_style,
        "model": model,
        "provider": provider,
        "eligible_count": len(names),
        "eligible_tools": names,
        "selected_raw": [],
        "selected_tools": [],
    }
    if not names:
        return [], meta

    menu = _build_menu(eligible_defs)
    messages = _build_selection_messages(menu, prompt_text, prompt_style=prompt_style)
    raw = (llm_call(messages) or "").strip()
    selected_raw = _parse_json_array(raw)
    selected = _clamp_to_known(selected_raw, names)
    meta["selected_raw"] = selected_raw
    meta["selected_tools"] = selected
    return selected, meta
