"""Read-only probes of the production router; classification may call an LLM."""
from __future__ import annotations

import time
from typing import Any

from src.handlers.handler_v2 import HandlerV2
from src.routing.skillset_router import SkillsetRouter


class _ProbeConfig:
    def __init__(self, config, overrides):
        self.config, self.overrides = config, overrides

    def get(self, key, default=None):
        value = self.config.get(key, default)
        if key == "request_routing":
            return {**(value or {}), **self.overrides}
        return value


class RoutingProbeHandler(HandlerV2):
    """Test routing without running agents or writing dialogue state."""

    def __init__(self, config):
        self.config = config

    @classmethod
    def name(cls):
        return "routing_probe"

    @classmethod
    def tool_def(cls):
        nullable_string = {"type": ["string", "null"]}
        properties = {
            "cases": {
                "type": "array", "minItems": 1, "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": {
                        "prompt_text": {"type": "string", "minLength": 1, "maxLength": 12000},
                        "expected_agent": dict(nullable_string),
                    },
                    "required": ["prompt_text", "expected_agent"],
                    "additionalProperties": False,
                },
            },
            "requested_agent": {**nullable_string, "description": "Fallback agent; null uses routing configuration."},
            "conversation_id": {**nullable_string, "description": "Existing session in the caller's account; null tests without history."},
            "context_name": {**nullable_string, "description": "Explicit context pins routing; null tests normal automatic selection."},
            "model": {**nullable_string, "description": "Optional classifier model override for this probe only."},
            "provider": {**nullable_string, "description": "Optional classifier provider override for this probe only."},
        }
        return {
            "type": "function", "name": cls.name(), "strict": True,
            "description": "Test 1-10 prompt strings through the real automatic router. Reports decisions and bounded classifier output/errors. May make paid LLM calls; never executes selected agents or changes session dialogue. Cases are independent, not a simulated conversation.",
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False},
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {"ok": {"type": "boolean"},
                "tool": {"type": "string"}, "results": {"type": "array"}},
                "required": ["ok", "tool"], "additionalProperties": True}

    def execute(self, args: dict[str, Any], *, account_name="auto", **context):
        def failure(message):
            return {"ok": False, "tool": self.name(), "error": message}

        cases = args.get("cases")
        if not isinstance(cases, list) or not 1 <= len(cases) <= 10:
            return failure("cases must contain 1-10 test cases")
        for case in cases:
            if not isinstance(case, dict):
                return failure("Each case must be an object")
            prompt = case.get("prompt_text")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
                return failure("Each prompt_text must contain 1-12000 characters")
            expected = case.get("expected_agent")
            if expected is not None and (not isinstance(expected, str) or not expected.strip()):
                return failure("expected_agent must be a non-empty string or null")
        for key in ("requested_agent", "conversation_id", "context_name", "model", "provider"):
            if args.get(key) is not None and not isinstance(args[key], str):
                return failure(f"{key} must be a string or null")
        manager, adapter = context.get("agent_manager"), context.get("llm_adapter")
        if manager is None or adapter is None:
            return failure("routing_probe requires agent_manager and llm_adapter")
        if not account_name or account_name == "auto":
            return failure("A request account is required")
        overrides = {key: args[key].strip() for key in ("model", "provider") if args.get(key)}
        # A model override without provider must infer its own provider, rather
        # than inheriting the configured routing provider for another model.
        if overrides.get("model") and "provider" not in overrides:
            overrides["provider"] = None
        router = SkillsetRouter(manager, _ProbeConfig(self.config, overrides), adapter,
                               context.get("episodic_store"))
        session_id = args.get("conversation_id")
        if session_id and context.get("episodic_store") is None:
            return failure("Session probes require episodic_store")
        results = []
        for case in cases:
            diagnostics = {}
            payload = {"routing": "auto", "accountName": account_name,
                       "agentName": args.get("requested_agent") or "",
                       "question": case["prompt_text"],
                       "conversationId": session_id,
                       "contextName": args.get("context_name")}
            started = time.monotonic()
            item = {"prompt_text": case["prompt_text"], "expected_agent": case.get("expected_agent")}
            try:
                decision = router.route(payload, diagnostics=diagnostics)
                item.update(decision.to_dict())
                item["ok"] = decision.reason not in {"classifier_failure", "history_failure"}
                if decision.direct_response is not None:
                    item["direct_response"] = decision.direct_response
                if case.get("expected_agent"):
                    item["matches_expected"] = (not decision.clarification and
                        decision.selected_agent == case["expected_agent"].strip().lower())
            except ValueError as exc:
                item.update(ok=False, error=str(exc))
            item.update(diagnostics=diagnostics, elapsed_ms=int((time.monotonic() - started) * 1000))
            results.append(item)
        return {"ok": all(item["ok"] for item in results), "tool": self.name(),
                "catalog": router.catalog(), "results": results,
                "classifier_calls": sum(item.get("classifier_calls", 0) for item in results)}
