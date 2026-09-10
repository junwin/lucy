from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Protocol

import requests

from .node import WorkflowNode
from .result import WorkflowResult


class WorkflowExecutor(Protocol):
    def execute(self, node: WorkflowNode) -> WorkflowResult:
        ...


class FakeWorkflowExecutor:
    """Deterministic scripted executor for unit tests and workflow dry runs."""

    def __init__(self, results: Mapping[str, WorkflowResult | Iterable[WorkflowResult]]):
        self._results: Dict[str, Deque[WorkflowResult]] = {}
        for node_id, value in results.items():
            if isinstance(value, WorkflowResult):
                queue = deque([value])
            else:
                queue = deque(value)
            self._results[node_id] = queue
        self.calls: list[str] = []
        self.feedback_seen: Dict[str, list[str]] = defaultdict(list)

    def execute(self, node: WorkflowNode) -> WorkflowResult:
        self.calls.append(node.id)
        feedback = node.metadata.get("feedback")
        if feedback:
            self.feedback_seen[node.id].append(str(feedback))
        queue = self._results.get(node.id)
        if not queue:
            raise RuntimeError(f"No fake result configured for workflow node '{node.id}'")
        if len(queue) == 1:
            return queue[0]
        return queue.popleft()


class AskWorkflowExecutor:
    """Run workflow work through Lucy's public ``/ask`` boundary.

    One call per node. The node's instructions are the question and the
    response text is the node's result. Nothing is read from or written to disk.

    A node succeeds unless ``/ask`` itself reports a system fault: a missing or
    rejected API key, a transport failure, a non-200 status, or an error body.

    Authentication defaults to reading ``api_key`` from ``config.local.json``
    and sending it in Lucy's primary ``X-API-Key`` request header.
    """

    def __init__(
        self,
        *,
        account_name: str,
        ask_url: str = "http://127.0.0.1:5000/ask",
        default_agent: str = "peace",
        default_context: str = "lucyproject",
        timeout: float = 300.0,
        config_path: str | Path = "config.local.json",
        api_key: str | None = None,
        post: Callable[..., Any] | None = None,
    ) -> None:
        self.account_name = account_name
        self.ask_url = ask_url
        self.default_agent = default_agent
        self.default_context = default_context
        self.timeout = timeout
        self.config_path = Path(config_path)
        self.api_key = api_key.strip() if api_key is not None else self._load_api_key(self.config_path)
        self._post = post or requests.post

    def execute(self, node: WorkflowNode) -> WorkflowResult:
        if not self.api_key:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error=(
                    "Lucy API key is missing. Expected non-empty 'api_key' in "
                    f"{self.config_path}"
                ),
            )

        agent_name = (node.agent_name or self.default_agent).strip()
        context_name = (node.context_name or self.default_context).strip()
        payload = {
            "question": self._question(node),
            "agentName": agent_name,
            "accountName": self.account_name,
            "contextName": context_name,
        }

        try:
            response = self._post(
                self.ask_url,
                json=payload,
                headers={"X-API-Key": self.api_key},
                timeout=self.timeout,
            )
        except Exception as exc:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error=f"/ask request failed: {exc}",
            )

        ask_body = self._response_body(response)
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code != 200:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                text=self._ask_text(ask_body),
                error=f"/ask returned HTTP {status_code}: {self._ask_error(ask_body)}",
            )

        if not isinstance(ask_body, dict):
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error="/ask returned HTTP 200 but the response body was not a JSON object",
            )

        if ask_body.get("error"):
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error=f"/ask reported an error: {ask_body.get('error')}",
            )

        return WorkflowResult(
            execution_state="completed",
            outcome="success",
            text=str(ask_body.get("response") or "").strip(),
            metrics={},
        )

    @staticmethod
    def _question(node: WorkflowNode) -> str:
        question = node.instructions.strip()
        feedback = node.metadata.get("feedback")
        if isinstance(feedback, str) and feedback.strip():
            question = f"{question}\n\nReview feedback from the previous attempt:\n{feedback.strip()}".strip()
        return question

    @staticmethod
    def _load_api_key(config_path: Path) -> str:
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(data, dict):
            return ""
        return str(data.get("api_key") or "").strip()

    @staticmethod
    def _response_body(response: Any) -> Any:
        try:
            return response.json()
        except Exception:
            return None

    @staticmethod
    def _ask_text(body: Any) -> str:
        if isinstance(body, dict):
            return str(body.get("response") or "")
        return ""

    @staticmethod
    def _ask_error(body: Any) -> str:
        if isinstance(body, dict):
            return str(body.get("error") or body.get("response") or body)
        return "non-JSON response"
