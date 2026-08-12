"""remote_execute — query a remote Lucy instance via its /ask endpoint.

Reads machine definitions from ``config.local.machines.json`` (a separate,
gitignored file because it holds API keys). Query-only: no reset, list, or
event sub-actions.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2


logger = logging.getLogger(__name__)


class RemoteExecuteHandler(HandlerV2):
    NAME = "remote_execute"
    DEFAULT_TIMEOUT = 120  # seconds; remote /ask is an LLM round trip

    def __init__(self, config: ConfigManager, machines_config_path: Optional[str] = None):
        self.config = config
        self._machines_config_path = machines_config_path

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Send a query to a remote Lucy instance (configured in "
                "config.local.machines.json) and return the final answer text. "
                "Query-only — no session reset, list, or event actions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "machine": {
                        "type": "string",
                        "description": "Machine key in config.local.machines.json (e.g. 'pi4').",
                    },
                    "question": {
                        "type": "string",
                        "description": "The query to send to the remote Lucy.",
                    },
                    "agentName": {
                        "type": "string",
                        "description": "Optional override for the remote agent name (defaults to the machine's default_agent). Use empty string to accept the default.",
                    },
                    "contextName": {
                        "type": "string",
                        "description": "Optional override for the remote context name (defaults to the machine's default_context). Use empty string to accept the default.",
                    },
                    "accountName": {
                        "type": "string",
                        "description": "Optional override for the remote account name (defaults to the caller's account). Use empty string to accept the default.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout in seconds for the remote request.",
                        "default": 120,
                    },
                },
                "required": [
                    "machine",
                    "question",
                    "agentName",
                    "contextName",
                    "accountName",
                    "timeout_seconds",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "machine": {"type": "string"},
                "question": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        machine_key = (args.get("machine") or "").strip()
        question = (args.get("question") or "").strip()

        if not machine_key:
            return self._error("machine is required", question=question)
        if not question:
            return self._error("question is required", machine=machine_key)

        machines = self._load_machines()
        machine = machines.get(machine_key)
        if not machine:
            available = ", ".join(sorted(machines.keys())) or "(none)"
            return self._error(
                f"Unknown machine '{machine_key}'. Available machines: {available}",
                machine=machine_key,
                question=question,
            )

        scheme = (machine.get("scheme") or "http").strip().rstrip(":/")
        host = (machine.get("host") or "").strip()
        port = machine.get("port", 5000)
        api_key = (machine.get("api_key") or "").strip()
        session_id = (machine.get("session_id") or "").strip()

        if not host:
            return self._error(
                f"Machine '{machine_key}' is missing a 'host'.",
                machine=machine_key,
                question=question,
            )

        # Fixed session reuse: NEVER generate a new UUID here.
        agent_name = (args.get("agentName") or machine.get("default_agent") or "").strip()
        context_name = (args.get("contextName") or machine.get("default_context") or "").strip()
        remote_account = (args.get("accountName") or "").strip() or account_name

        body = {
            "question": question,
            "accountName": remote_account,
            "agentName": agent_name,
            "contextName": context_name,
            "sessionId": session_id,
        }

        url = f"{scheme}://{host}:{port}/ask"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }

        timeout = args.get("timeout_seconds") or self.DEFAULT_TIMEOUT
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = self.DEFAULT_TIMEOUT

        try:
            resp = requests.post(url, json=body, headers=headers, timeout=timeout)
            resp.raise_for_status()
            raw = resp.text or ""
        except requests.exceptions.Timeout:
            return self._error(
                f"Remote request timed out after {timeout}s.",
                machine=machine_key,
                question=question,
            )
        except requests.exceptions.RequestException as e:
            return self._error(
                f"Remote request failed: {e}",
                machine=machine_key,
                question=question,
            )

        answer = self._parse_response(raw)
        if answer is None:
            return self._error(
                "Could not find a final message in the remote response.",
                machine=machine_key,
                question=question,
                raw=raw[:500],
            )

        return {
            "ok": True,
            "tool": self.NAME,
            "machine": machine_key,
            "question": question,
            "result": answer,
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _error(self, message: str, *, machine: str = "", question: str = "", **extra: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": False,
            "tool": self.NAME,
            "error": message,
            "machine": machine,
            "question": question,
        }
        result.update(extra)
        return result

    def _machines_path(self) -> str:
        if self._machines_config_path:
            return self._machines_config_path
        base_dir = os.path.dirname(os.path.abspath(self.config.file_name))
        return os.path.join(base_dir, "config.local.machines.json")

    def _load_machines(self) -> Dict[str, Dict[str, Any]]:
        path = self._machines_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("remote_execute: failed to load machines config %s: %s", path, e)
            return {}

        machines = data.get("machines", {}) if isinstance(data, dict) else {}
        return machines if isinstance(machines, dict) else {}

    def _parse_response(self, raw: str) -> Optional[str]:
        """Extract the final answer from an SSE or plain-JSON /ask response.

        SSE format is ``data: {json}\\n\\n``. Accepts both a remote ``kind``
        field (``"message"``) and the local ``type`` field (``"text"``).
        Falls back to the non-streaming JSON ``{"response": "..."}`` shape.
        """
        text = (raw or "").strip()
        if not text:
            return None

        # Non-streaming JSON fallback.
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and obj.get("response"):
            return str(obj["response"])

        # SSE path.
        messages: list = []
        errors: list = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload:
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            kind = event.get("kind") or event.get("type")
            if kind in ("message", "text"):
                content = (
                    event.get("content")
                    or event.get("message")
                    or event.get("text")
                    or event.get("result")
                )
                if content:
                    messages.append(str(content))
            elif kind == "error":
                err = event.get("message") or event.get("error") or event.get("content")
                if err:
                    errors.append(str(err))

        if messages:
            return messages[-1]
        if errors:
            return f"[remote error] {errors[-1]}"
        return None

    def execute_raw(self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "", **context: Any) -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(args if isinstance(args, dict) else {}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)
