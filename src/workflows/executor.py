from __future__ import annotations

import json
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Protocol

import requests

from src.tasklists.task import Task
from src.tasklists.task_list import TaskList

from .node import WorkflowNode
from .result import VALID_OUTCOMES, WorkflowResult


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


def classify_semantic_outcome(text: str, execution_state: str) -> str:
    """Classify semantic outcome without equating normal execution with success."""
    if execution_state != "completed":
        return "failed"

    raw = (text or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                outcome = str(payload.get("outcome") or "").strip().lower()
                if outcome in VALID_OUTCOMES:
                    return outcome
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    lowered = raw.lower()
    blocked_markers = (
        "blocked",
        "cannot access",
        "can't access",
        "could not access",
        "unable to access",
        "cannot complete",
        "could not complete",
        "unable to complete",
    )
    if any(marker in lowered for marker in blocked_markers):
        return "blocked"
    return "inconclusive"


class AskWorkflowExecutor:
    """Run workflow work through Lucy's public ``/ask`` boundary.

    Authentication defaults to reading ``api_key`` from ``config.local.json``
    and sending it in Lucy's primary ``X-API-Key`` request header.
    """

    _ADDITIVE_METRIC_KEYS = (
        "iterations",
        "openai_calls",
        "tool_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "failures",
        "errors",
        "warnings",
        "duration_ms",
    )

    def __init__(
        self,
        *,
        account_name: str,
        tasklist_dir: str | Path,
        ask_url: str = "http://127.0.0.1:5000/ask",
        default_agent: str = "peace",
        default_context: str = "lucyproject",
        timeout: float = 300.0,
        config_path: str | Path = "config.local.json",
        api_key: str | None = None,
        post: Callable[..., Any] | None = None,
    ) -> None:
        self.account_name = account_name
        self.tasklist_dir = Path(tasklist_dir)
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

        tasklist_id = node.tasklist_id
        if not tasklist_id:
            tasklist_id = f"workflow-{node.id}-{uuid.uuid4().hex[:8]}"
            self._write_generated_tasklist(tasklist_id, node)

        history_path = self.tasklist_dir / f"{tasklist_id}.jsonl"
        before_count = self._valid_line_count(history_path)

        agent_name = (node.agent_name or self.default_agent).strip()
        context_name = (node.context_name or self.default_context).strip()
        payload = {
            "question": (
                f'Use the tasklists_run tool to run tasklist "{tasklist_id}" '
                f'in multi-step mode with worker_agent "{agent_name}". '
                "Report the outcome."
            ),
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

        ask_text = str(ask_body.get("response") or "").strip()
        new_records = self._read_records_after(history_path, before_count)
        if not new_records:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                text=ask_text,
                error=(
                    f"/ask returned successfully but tasklist '{tasklist_id}' produced no new "
                    f"execution records in {history_path}"
                ),
            )

        execution_state = (
            "completed"
            if all(str(record.get("state") or "").lower() == "completed" for record in new_records)
            else "error"
        )
        last_record = new_records[-1]
        text = self._result_text(last_record)
        metrics = self._aggregate_metrics(new_records)
        outcome = classify_semantic_outcome(text, execution_state)
        error = self._first_record_error(new_records)

        return WorkflowResult(
            execution_state=execution_state,
            outcome=outcome,
            text=text,
            metrics=metrics,
            error=error,
        )

    @staticmethod
    def _load_api_key(config_path: Path) -> str:
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(data, dict):
            return ""
        return str(data.get("api_key") or "").strip()

    def _write_generated_tasklist(self, tasklist_id: str, node: WorkflowNode) -> None:
        self.tasklist_dir.mkdir(parents=True, exist_ok=True)
        task = Task(
            id=f"{node.id}-work",
            name=node.name,
            instructions=self._instructions_with_feedback(node),
            agent=node.agent_name or self.default_agent,
            context=node.context_name or self.default_context,
        )
        tasklist = TaskList(
            id=tasklist_id,
            name=f"Workflow: {node.name}",
            description=f"Generated by WorkflowRunner for node {node.id}",
            tasks=[task],
            meta={"workflow_node_id": node.id},
        )
        path = self.tasklist_dir / f"{tasklist_id}.json"
        path.write_text(tasklist.to_json(), encoding="utf-8")

    @staticmethod
    def _instructions_with_feedback(node: WorkflowNode) -> str:
        instructions = node.instructions.strip()
        feedback = str(node.metadata.get("feedback") or "").strip()
        if feedback:
            instructions = f"{instructions}\n\nReview feedback from the previous attempt:\n{feedback}".strip()
        return instructions

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

    @staticmethod
    def _valid_line_count(path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    count += 1
        return count

    @staticmethod
    def _read_records_after(path: Path, valid_record_offset: int) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        seen_valid = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if seen_valid >= valid_record_offset:
                    records.append(record)
                seen_valid += 1
        return records

    @classmethod
    def _aggregate_metrics(cls, records: list[dict[str, Any]]) -> dict[str, Any]:
        aggregate: dict[str, Any] = {}
        for record in records:
            metrics = record.get("metrics")
            if not isinstance(metrics, dict):
                continue
            for key in cls._ADDITIVE_METRIC_KEYS:
                value = metrics.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    aggregate[key] = aggregate.get(key, 0) + value
            for key in (
                "agent",
                "account",
                "session_id",
                "correlation_id",
                "max_iterations",
                "hit_iteration_cap",
            ):
                if key in metrics:
                    aggregate[key] = metrics[key]
        return aggregate

    @staticmethod
    def _result_text(record: dict[str, Any]) -> str:
        result = record.get("result")
        if isinstance(result, dict):
            output = result.get("output")
            if output is not None:
                return str(output)
            if result:
                return json.dumps(result, default=str)
        if result is not None:
            return str(result)
        return ""

    @staticmethod
    def _first_record_error(records: list[dict[str, Any]]) -> str | None:
        for record in records:
            error = record.get("error")
            if error:
                return str(error)
        return None
