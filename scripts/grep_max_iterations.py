#!/usr/bin/env python3
"""Analyze FunctionCallingProcessor loop iterations from the log file."""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "my_log_file.log"

ITER_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ .*"
    r" - FunctionCallingProcessor\(streaming\): (?:tool_call )?iteration=(\d+)/(\d+)"
    r" correlation_id=([0-9a-f-]+) agent=(\S+) session_id=([0-9a-f-]+)"
)


def parse_log(path):
    requests = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            match = ITER_RE.search(line)
            if match is None:
                continue
            timestamp, iteration, cap, correlation_id, agent, session_id = match.groups()
            iteration = int(iteration)
            cap = int(cap)
            entry = requests.get(correlation_id)
            if entry is None:
                entry = {
                    "correlation_id": correlation_id,
                    "agent": agent,
                    "session_id": session_id,
                    "max_iteration": 0,
                    "cap": 0,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                }
                requests[correlation_id] = entry
            entry["last_seen"] = timestamp
            if iteration > entry["max_iteration"]:
                entry["max_iteration"] = iteration
                entry["cap"] = cap
    return list(requests.values())


def main():
    parser = argparse.ArgumentParser(
        description="Show the maximum number of FunctionCallingProcessor "
        "iterations used per request, from the log file"
    )
    parser.add_argument("--log-file", default=str(DEFAULT_LOG), help="path to log file")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="show the top N requests by max iteration (default: %(default)s)",
    )
    parser.add_argument(
        "--min-iterations",
        type=int,
        default=0,
        help="only show requests using at least N iterations (default: %(default)s)",
    )
    parser.add_argument("--agent", help="only show requests for this agent")
    parser.add_argument("--correlation-id", help="only show requests with this correlation id")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.is_file():
        print(f"error: log file not found: {log_path}", file=sys.stderr)
        return 2

    requests = parse_log(log_path)
    if args.agent:
        requests = [r for r in requests if r["agent"] == args.agent]
    if args.correlation_id:
        requests = [r for r in requests if r["correlation_id"] == args.correlation_id]
    requests.sort(key=lambda r: r["max_iteration"], reverse=True)

    if not requests:
        print("no iteration records found")
        return 0

    overall = requests[0]
    capped = [r for r in requests if r["max_iteration"] >= r["cap"]]
    print(
        f"overall max iterations: {overall['max_iteration']}/{overall['cap']} "
        f"correlation_id={overall['correlation_id']} agent={overall['agent']} "
        f"session_id={overall['session_id']} last_seen={overall['last_seen']}"
    )
    print(f"requests analyzed: {len(requests)}  (hit iteration cap: {len(capped)})")
    print()

    shown = [r for r in requests if r["max_iteration"] >= args.min_iterations][: args.top]
    if not shown:
        print(f"no requests with max_iteration >= {args.min_iterations}")
        return 0

    print(f"requests by max iteration (top {len(shown)}):")
    for index, r in enumerate(shown, 1):
        flag = " (capped)" if r["max_iteration"] >= r["cap"] else ""
        print(
            f"{index:>3}. {r['max_iteration']:>2}/{r['cap']:<2} "
            f"correlation_id={r['correlation_id']} agent={r['agent']} "
            f"session_id={r['session_id']} first={r['first_seen']} last={r['last_seen']}{flag}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
