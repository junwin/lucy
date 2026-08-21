"""LLM-based tool suggestion for the tool selection pipeline (issue #126).

Stage 6 of the approved design (``software/ai/lucy/design/tool-selection-pipeline.md``,
section 5.4): given the user request text and the eligible tool definitions,
build a compact "name — first sentence" menu, ask a cheap LLM to pick the
minimal active subset, and clamp the reply back to the eligible names.

Pure functions only, no regex expansion rules (D3): the "three sisters",
tasklist pair, and ``file_refs``/``git_ops``/``cli_run`` heuristics are gone.
Empty-result behaviour and the "too small to bother" skip threshold live in
the pipeline (``pipeline.py``), not here.

The ``llm_call`` contract
-------------------------
``llm_call(messages) -> str`` receives the selection messages (a list of
``{"role": ..., "content": ...}`` dicts) and returns the raw reply text.
``model`` / ``provider`` are recorded in ``meta`` for observability; the
caller is responsible for binding them into ``llm_call`` (see
``resolve_llm_target`` in ``pipeline.py``).

LLM failures are NOT swallowed here: exceptions from ``llm_call`` propagate
so the pipeline can fall back to required-only per D5.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["suggest_tools"]


# Selection prompt strategies. Kept as data so variants are easy to swap.
_SELECTION_PROMPTS: Dict[str, str] = {
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


def _build_selection_messages(
    menu: str,
    prompt_text: str,
    prompt_style: str = "verb_first",
) -> List[Dict[str, str]]:
    system = _SELECTION_PROMPTS.get(prompt_style, _SELECTION_PROMPTS["verb_first"])
    user = (
        f"TOOLS:\n{menu}\n\n"
        f"REQUEST:\n{prompt_text}\n\n"
        "Return only a JSON array of tool names."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_json_array(text: str) -> List[str]:
    """Best-effort extraction of a JSON array of strings.

    Handles the common ways small LLMs drift from strict JSON:
      - ``["file_load", "file_save"]`` (valid JSON)
      - ``[file_load, file_save]``        (unquoted names)
      - ``['file_load', 'file_save']``    (single-quoted names)
      - ``[tasklists_manage]``            (bare unquoted name)
      - ``file_load``                     (bare single name, no brackets)
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    text = text.strip("`")

    # 1) Strict JSON (also covers the plain ``["a", "b"]`` case).
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass

    # Extract bracket contents if present, so surrounding prose doesn't leak in.
    inner = text
    m = re.search(r"\[(.*)\]", text, flags=re.DOTALL)
    if m:
        inner = m.group(1)

    # 2) Double-quoted strings.
    arr = re.findall(r'"([^"]+)"', inner)
    if arr:
        return [x.strip() for x in arr if x.strip()]

    # 3) Single-quoted strings.
    arr = re.findall(r"'([^']+)'", inner)
    if arr:
        return [x.strip() for x in arr if x.strip()]

    # 4) Unquoted, comma/whitespace separated names inside brackets.
    if m:
        tokens = re.split(r"[,\s]+", inner.strip())
        return [t.strip() for t in tokens if t.strip()]

    # 5) Bare single name with no separators.
    if not re.search(r"[,\s]", inner):
        return [inner.strip()] if inner.strip() else []

    return []


def _clamp_to_known(names: List[str], known: List[str]) -> List[str]:
    """Clamp LLM output to ``known`` names: dedup, in ``known`` (eligible) order.

    Names the LLM invented or that are not eligible are dropped; the result is
    ordered by ``known`` so the pipeline's active set stays deterministic.
    """
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
    """Suggest the minimal active tool subset via a cheap LLM call.

    Builds the compact "name — first sentence" menu from ``eligible_defs``,
    asks ``llm_call`` to pick from it, then clamps the parsed reply to the
    eligible tool names (dedup, eligible order preserved).

    Returns ``(selected_names, meta)`` where ``selected_names`` is the clamped
    suggestion (possibly empty — empty-result behaviour lives in the pipeline)
    and ``meta`` records the prompt style, model/provider, eligible names, and
    the raw parsed reply for observability.

    When ``eligible_defs`` is empty the LLM is never called; an empty
    suggestion is returned (the pipeline owns skip thresholds / fallbacks).

    Raises: any exception from ``llm_call`` propagates (the pipeline falls
    back to required-only per D5).
    """
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
        # Nothing to choose from — never call the LLM with an empty menu.
        return [], meta

    menu = _build_menu(eligible_defs)
    messages = _build_selection_messages(menu, prompt_text, prompt_style=prompt_style)
    raw = (llm_call(messages) or "").strip()
    selected_raw = _parse_json_array(raw)
    selected = _clamp_to_known(selected_raw, names)
    meta["selected_raw"] = selected_raw
    meta["selected_tools"] = selected
    return selected, meta
