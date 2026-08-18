"""Lazy tool selection for the FunctionCallingProcessor.

Given the user's request text and the eligible tool definitions, ask a cheap
LLM to pick the minimal active subset, then apply deterministic expansion rules
("three sisters", file_refs, git_ops) to recover tools the LLM under-selected.
The result is the reduced set of *full* tool definitions so the main model only
receives the schemas it is likely to need.

The selection LLM call is intentionally cheap: it sends only a compact
"name — first-sentence-description" menu, NOT the full JSON schemas.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

# Tools grouped by the "three sisters" rule: when any one is selected, all
# three are added (when eligible).
THREE_SISTERS = ("file_load", "file_save", "execute_command")

# The "tasklist pair": tasklists_manage and tasklists_run almost always
# travel together (manage defines/updates a list, run executes it). When
# either one is selected, add both (when eligible).
TASKLIST_SISTERS = ("tasklists_manage", "tasklists_run")


def estimate_tokens(text: str) -> int:
    """Mirror src.prompt_builders.prompt_builder.estimate_tokens_from_text (len/4).

    Kept local so this module stays importable without optional deps.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


# Deterministic prompt-based expansion rules.
#
# Each rule has:
#   pattern — compiled regex matched against the request text (case-insensitive)
#   expand  — tuple of tool names to add when the pattern matches (if eligible)
#   why     — human-readable rationale for reporting/debugging
_RULES: List[Dict[str, Any]] = [
    {
        "name": "file_refs",
        "pattern": re.compile(
            r"\b(file|files|obsidian|note|notes|document|documents|read|log|logs)\b"
            r"|\.md|\.txt|\.py|\.json|\.csv|\.log|\.yml|\.yaml|\.toml|\.ini",
            re.IGNORECASE,
        ),
        "expand": THREE_SISTERS,
        "why": "File-ish signals imply file_load, and usually the sisters.",
    },
    {
        "name": "git_ops",
        "pattern": re.compile(
            r"\b(git|github|commit|commits|push|pushes|pull|branch|branches|merge|merges|"
            r"pull request|pr|clone|clones|checkout|repo|repos|repository|repositories|"
            r"rebase)\b",
            re.IGNORECASE,
        ),
        "expand": ("execute_command",),
        "why": "Git/GitHub operations run through the shell via execute_command.",
    },
    {
        "name": "cli_run",
        "pattern": re.compile(
            r"\b(cli|post)\b",
            re.IGNORECASE,
        ),
        "expand": THREE_SISTERS,
        "why": "operation running a cli need execute_command and usually file_load and file_save",
    },
]


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
    known_set = set(known)
    out: List[str] = []
    for n in names:
        if n in known_set and n not in out:
            out.append(n)
    return out


def _apply_sister_group(
    selected: List[str], known: List[str], group: Tuple[str, ...]
) -> List[str]:
    """If any member of ``group`` is selected, add all eligible members.

    Preserves ``known`` ordering so the final active set is deterministic.
    """
    known_set = set(known)
    members = [n for n in group if n in known_set]
    selected_set = set(selected)
    if not (selected_set & set(members)):
        return selected
    selected_set.update(members)
    return [n for n in known if n in selected_set]


def _apply_rules(
    prompt_text: str,
    selected: List[str],
    known: List[str],
) -> Tuple[List[str], List[str], List[str]]:
    """Apply deterministic prompt-based rules on top of the LLM pick.

    Returns ``(new_selected, hits, added)`` where ``hits`` are the rule names
    whose pattern matched and ``added`` are the tool names the rules actually
    added. Ordering follows ``known``.
    """
    known_set = set(known)
    selected_set = set(selected)
    hits: List[str] = []
    added: List[str] = []
    for rule in _RULES:
        if rule["pattern"].search(prompt_text):
            hits.append(rule["name"])
            for n in rule["expand"]:
                if n in known_set and n not in selected_set:
                    selected_set.add(n)
                    added.append(n)
    new_selected = [n for n in known if n in selected_set]
    return new_selected, hits, added


def _tokens(value: Any) -> int:
    """Token estimate for a value, using the same len/4 heuristic as the FCP."""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    return estimate_tokens(text)


def select_active_tool_defs(
    prompt_text: str,
    eligible_defs: List[Dict[str, Any]],
    *,
    llm_call: Callable[[List[Dict[str, str]]], str],
    prompt_style: str = "verb_first",
    three_sisters: bool = True,
    tasklist_pair: bool = True,
    rules: bool = True,
    min_eligible_to_select: int = 5,
    allow_empty_active_set: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Pick the minimal active tool subset and return (active_defs, meta).

    - When ``eligible_defs`` is empty, or too small to be worth selecting
      (``len < min_eligible_to_select``), the full ``eligible_defs`` is returned
      unchanged with ``meta["skipped"] = True``.
    - When the selection result is empty and ``allow_empty_active_set`` is
      False, the full ``eligible_defs`` is returned as a safety fallback so the
      main model never loses tool access entirely (under-selection protection).

    ``llm_call`` receives the compact selection messages (list of {role,content})
    and must return the raw text of the LLM reply.
    """
    if not eligible_defs:
        return eligible_defs, {"skipped": True, "reason": "empty_eligible", "eligible_count": 0}

    if len(eligible_defs) < min_eligible_to_select:
        return eligible_defs, {
            "skipped": True,
            "reason": "below_threshold",
            "eligible_count": len(eligible_defs),
        }

    names = [td.get("name") for td in eligible_defs]
    menu = _build_menu(eligible_defs)
    messages = _build_selection_messages(menu, prompt_text, prompt_style=prompt_style)

    raw = (llm_call(messages) or "").strip()
    selected_raw = _parse_json_array(raw)
    selected = _clamp_to_known(selected_raw, names)
    selected_before_sisters = list(selected)
    if three_sisters:
        selected = _apply_sister_group(selected, names, THREE_SISTERS)
    if tasklist_pair:
        selected = _apply_sister_group(selected, names, TASKLIST_SISTERS)
    selected_before_rules = list(selected)

    rules_hits: List[str] = []
    rules_added: List[str] = []
    if rules:
        selected, rules_hits, rules_added = _apply_rules(prompt_text, selected, names)

    # Safety: an empty active set would disable tool use entirely. Unless the
    # caller explicitly opted into aggressive mode, fall back to the full set.
    if not selected and not allow_empty_active_set:
        meta: Dict[str, Any] = {
            "skipped": True,
            "reason": "empty_selection_fallback",
            "eligible_count": len(eligible_defs),
        }
        return eligible_defs, meta

    active_defs = [td for td in eligible_defs if td.get("name") in set(selected)]

    eligible_tokens = _tokens(eligible_defs)
    active_tokens = _tokens(active_defs)
    selection_input_tokens = _tokens(messages)
    savings_tokens = max(0, eligible_tokens - active_tokens)
    savings_pct = round(100.0 * savings_tokens / eligible_tokens, 1) if eligible_tokens else 0.0
    net_savings = savings_tokens - selection_input_tokens

    meta = {
        "skipped": False,
        "eligible_count": len(eligible_defs),
        "eligible_tools": names,
        "selected_tools": selected,
        "selected_raw": selected_raw,
        "selected_before_sisters": selected_before_sisters,
        "selected_before_rules": selected_before_rules,
        "rules_hits": rules_hits,
        "rules_added": rules_added,
        "active_count": len(selected),
        "tokens": {
            "eligible_schema_tokens": eligible_tokens,
            "active_schema_tokens": active_tokens,
            "selection_input_tokens": selection_input_tokens,
            "savings_tokens": savings_tokens,
            "savings_pct": savings_pct,
            "net_savings_tokens": net_savings,
        },
    }
    return active_defs, meta
