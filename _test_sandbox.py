"""Smoke test for sandbox_execute — all tools + continue_on_error."""
import json
from src.config_manager import ConfigManager
from src.handlers.registry_bootstrap import build_registry

config = ConfigManager("config.json")
reg = build_registry()
handler = reg.create("sandbox_execute", config=config)


def _print_steps(result):
    print(f"ok={result['ok']}, steps={len(result['steps'])}")
    for s in result["steps"]:
        print(f"  step {s['step']}: {s['tool']} ok={s['ok']}")
        r = s["result"]
        if s["ok"]:
            for k in r:
                v = str(r[k])[:150]
                print(f"    {k}: {v}")
        else:
            print(f"    error: {r.get('error', '?')[:200]}")


# ── Test 1: execute_command + file_load ────────────────────────────────
print("\n=== Test 1: execute_command + file_load ===")
result = handler.execute({
    "steps": [
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo hello_from_sandbox", "working_directory": ".",
            "timeout_seconds": 5, "success_exit_codes": [0],
        }},
        {"tool": "file_load", "args": {
            "location": "external", "external_root": "repo_lucy",
            "path": "_test_sandbox.py",
        }},
    ]
}, account_name="junwin", registry=reg)
_print_steps(result)
assert result["ok"]


# ── Test 2: web_search + get_keywords ──────────────────────────────────
print("\n=== Test 2: web_search + get_keywords ===")
result = handler.execute({
    "steps": [
        {"tool": "web_search_handler", "args": {
            "query": "Python asyncio best practices", "count": 3,
        }},
        {"tool": "get_keywords", "args": {
            "content": "$step_1.results", "top_n": 5, "language_code": "en",
        }},
    ]
}, account_name="junwin", registry=reg)
_print_steps(result)
assert result["ok"]


# ── Test 3: command stdout → get_keywords ──────────────────────────────
print("\n=== Test 3: command stdout → get_keywords ===")
result = handler.execute({
    "steps": [
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo 'machine learning deep neural networks transformers'",
            "working_directory": ".", "timeout_seconds": 5, "success_exit_codes": [0],
        }},
        {"tool": "get_keywords", "args": {
            "content": "$step_1.stdout", "top_n": 5, "language_code": "en",
        }},
    ]
}, account_name="junwin", registry=reg)
_print_steps(result)
assert result["ok"]


# ── Test 4: continue_on_error (default: stop on first error) ───────────
print("\n=== Test 4: stop on first error (default) ===")
result = handler.execute({
    "steps": [
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo ok1", "working_directory": ".",
            "timeout_seconds": 5, "success_exit_codes": [0],
        }},
        {"tool": "get_keywords", "args": {
            "content": "", "top_n": 5,  # empty → will fail
        }},
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo should_not_run", "working_directory": ".",
            "timeout_seconds": 5, "success_exit_codes": [0],
        }},
    ]
}, account_name="junwin", registry=reg)
_print_steps(result)
assert not result["ok"]
assert len(result["steps"]) == 2  # stopped at step 2, step 3 never ran


# ── Test 5: continue_on_error=true ─────────────────────────────────────
print("\n=== Test 5: continue_on_error=true ===")
result = handler.execute({
    "steps": [
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo ok1", "working_directory": ".",
            "timeout_seconds": 5, "success_exit_codes": [0],
        }},
        {"tool": "get_keywords", "args": {
            "content": "", "top_n": 5,  # empty → will fail, but we continue
        }},
        {"tool": "execute_command", "args": {
            "location": "external", "external_root": "repo_lucy",
            "command": "echo ok3_should_run", "working_directory": ".",
            "timeout_seconds": 5, "success_exit_codes": [0],
        }},
    ],
    "continue_on_error": True,
}, account_name="junwin", registry=reg)
_print_steps(result)
assert not result["ok"]  # overall still false because step 2 failed
assert len(result["steps"]) == 3  # all 3 steps ran
assert result["steps"][0]["ok"]
assert not result["steps"][1]["ok"]
assert result["steps"][2]["ok"]


print("\n=== All 5 tests passed ✅ ===")
