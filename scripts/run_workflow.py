#!/usr/bin/env python3
"""Load a YAML workflow definition and run it end to end.

The loader turns the YAML file into a WorkflowNode tree. The runner drives that
tree and calls executor.execute(node) once per leaf node visit.

Usage:
    python scripts/run_workflow.py
    python scripts/run_workflow.py --workflow workflows/issue_resolution.yaml
    python scripts/run_workflow.py --fake-outcome failed
    python scripts/run_workflow.py --fake-outcome "review=failed,success"
    python scripts/run_workflow.py --executor ask --account junwin

Exit codes:
    0  workflow completed with outcome success
    1  workflow failed, errored, or the definition was invalid
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflows import (
    AskWorkflowExecutor,
    FakeWorkflowExecutor,
    WorkflowLoader,
    WorkflowNode,
    WorkflowResult,
    WorkflowRunner,
)
from src.workflows.result import VALID_OUTCOMES

DEFAULT_WORKFLOW = "workflows/issue_resolution.yaml"
DEFAULT_ASK_URL = "http://127.0.0.1:5000/ask"
DEFAULT_ACCOUNT = "junwin"
EXECUTABLE_TYPES = {"condition", "tasklist", "retry"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load and run a YAML workflow definition.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Path to the workflow YAML file.")
    parser.add_argument(
        "--executor",
        choices=("fake", "ask"),
        default="fake",
        help="'fake' is a deterministic dry run; 'ask' calls a running Lucy instance.",
    )
    parser.add_argument(
        "--fake-outcome",
        default="success",
        help=(
            "Fake outcome script. A single outcome applies to every node. Use "
            "node=outcome,outcome;other=outcome to script one outcome per attempt "
            "for named nodes."
        ),
    )
    parser.add_argument(
        "--fake-tokens",
        type=int,
        default=0,
        help="total_tokens metric the fake executor reports for each node.",
    )
    parser.add_argument("--account", default=DEFAULT_ACCOUNT, help="Account name for the ask executor.")
    parser.add_argument("--agent", default=None, help="Fallback agent when a node defines none.")
    parser.add_argument("--context", default=None, help="Fallback context when a node defines none.")
    parser.add_argument("--ask-url", default=DEFAULT_ASK_URL, help="Lucy /ask endpoint.")
    parser.add_argument("--max-tokens", type=int, default=None, help="Optional workflow token budget.")
    return parser.parse_args(argv)


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (REPO_ROOT / path)


def parse_fake_script(spec: str) -> tuple[list[str], dict[str, list[str]]]:
    default: list[str] = []
    overrides: dict[str, list[str]] = {}

    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue

        node_id, separator, raw = chunk.partition("=")
        if separator:
            label = f"node '{node_id.strip()}'"
            outcomes = [part.strip() for part in raw.split(",") if part.strip()]
        else:
            label = "all nodes"
            outcomes = [chunk]

        if not outcomes:
            raise ValueError(f"Fake outcome script has no outcomes for {label}: '{chunk}'")

        for outcome in outcomes:
            if outcome not in VALID_OUTCOMES:
                raise ValueError(
                    f"Unsupported fake outcome '{outcome}' for {label}. "
                    f"Valid outcomes: {', '.join(sorted(VALID_OUTCOMES))}"
                )

        if separator:
            overrides[node_id.strip()] = outcomes
        else:
            default = outcomes

    if not default and not overrides:
        raise ValueError("Fake outcome script is empty")

    return default, overrides


def build_fake_results(
    root: WorkflowNode,
    default: list[str],
    overrides: dict[str, list[str]],
    fake_tokens: int,
) -> dict[str, list[WorkflowResult]]:
    nodes = {node.id: node for node in root.walk()}
    unknown = sorted(set(overrides) - set(nodes))
    if unknown:
        raise ValueError(f"Fake outcome script names unknown nodes: {', '.join(unknown)}")

    scripted: dict[str, list[WorkflowResult]] = {}
    for node_id, node in nodes.items():
        outcomes = overrides.get(node_id) or default or ["success"]
        if len(outcomes) > node.max_attempts and node.type in EXECUTABLE_TYPES:
            print(
                f"note: node '{node_id}' is scripted {len(outcomes)} outcomes "
                f"but max_attempts={node.max_attempts}",
                file=sys.stderr,
            )
        scripted[node_id] = [
            WorkflowResult(
                execution_state="completed",
                outcome=outcome,
                text=f"{node_id} attempt {attempt} outcome={outcome}",
                metrics={"total_tokens": fake_tokens, "iterations": 1},
            )
            for attempt, outcome in enumerate(outcomes, start=1)
        ]
    return scripted


def build_fake_executor(args: argparse.Namespace, root: WorkflowNode) -> tuple[FakeWorkflowExecutor, dict[str, list[WorkflowResult]]]:
    default, overrides = parse_fake_script(args.fake_outcome)
    scripted = build_fake_results(root, default, overrides, args.fake_tokens)
    return FakeWorkflowExecutor(scripted), scripted


def build_ask_executor(args: argparse.Namespace) -> AskWorkflowExecutor:
    return AskWorkflowExecutor(
        account_name=args.account,
        ask_url=args.ask_url,
        default_agent=args.agent or "peace",
        default_context=args.context or "lucyproject",
        config_path=REPO_ROOT / "config.local.json",
    )


def print_tree(root: WorkflowNode) -> None:
    print("Workflow tree")
    for node in root.walk():
        indent = "  " * _depth(node)
        print(f"{indent}- {node.id} ({node.type}) max_attempts={node.max_attempts}")


def print_script(root: WorkflowNode, scripted: dict[str, list[WorkflowResult]]) -> None:
    print("\nFake script")
    for node in root.walk():
        outcomes = [result.outcome for result in scripted.get(node.id, [])]
        print(f"  {node.id:<12} {' -> '.join(outcomes) if outcomes else '-'}")


def print_calls(executor: object) -> None:
    calls = getattr(executor, "calls", None)
    if calls is None:
        return
    print(f"\nExecutor calls ({len(calls)})")
    print(f"  {' -> '.join(calls) if calls else 'none'}")


def print_trace(root: WorkflowNode) -> None:
    print("\nNode trace")
    for node in root.walk():
        print(
            f"  {node.id:<12} type={node.type:<10} state={node.state:<10} "
            f"outcome={node.outcome or '-':<12} attempts={node.attempts}"
        )


def print_feedback(executor: object) -> None:
    print("\nFeedback propagation")
    feedback_seen = getattr(executor, "feedback_seen", None)
    if not feedback_seen:
        print("  none")
        return
    for node_id, messages in feedback_seen.items():
        print(f"  {node_id}: {len(messages)} message(s)")
        for message in messages:
            print(f"    - {message}")


def print_result(result: WorkflowResult, runner: WorkflowRunner) -> None:
    print("\nResult")
    print(f"  execution_state: {result.execution_state}")
    print(f"  outcome:         {result.outcome}")
    if result.error:
        print(f"  error:           {result.error}")
    if result.text:
        print(f"  text:            {result.text}")
    if result.metrics:
        print(f"  metrics:         {result.metrics}")
    print(f"  runner totals:   tokens={runner.total_tokens} iterations={runner.total_iterations}")


def _depth(node: WorkflowNode) -> int:
    depth = 0
    parent = node.parent
    while parent is not None:
        depth += 1
        parent = parent.parent
    return depth


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workflow_path = resolve_path(args.workflow)
    if not workflow_path.exists():
        print(f"Workflow file not found: {workflow_path}", file=sys.stderr)
        return 1

    print(f"Loading workflow: {workflow_path}")
    try:
        root = WorkflowLoader().load_file(workflow_path)
    except (ValueError, OSError) as exc:
        print(f"Workflow load failed: {exc}", file=sys.stderr)
        return 1

    print_tree(root)

    try:
        if args.executor == "fake":
            executor, scripted = build_fake_executor(args, root)
            print_script(root, scripted)
        else:
            executor = build_ask_executor(args)
    except ValueError as exc:
        print(f"Executor setup failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nExecutor: {type(executor).__name__}")

    runner = WorkflowRunner(executor, max_tokens=args.max_tokens)
    try:
        result = runner.run(root)
    except Exception as exc:
        print(f"Workflow run raised: {exc}", file=sys.stderr)
        return 1

    print_calls(executor)
    print_trace(root)
    print_feedback(executor)
    print_result(result, runner)
    return 0 if result.outcome == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
