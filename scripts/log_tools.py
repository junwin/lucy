#!/usr/bin/env python3
"""Inspect Lucy log messages and tool calls by correlation id."""
import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "my_log_file.log"

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
CORRELATION_RE = re.compile(r"correlation_id=([0-9a-fA-F-]{36})")

INBOUND_RE = re.compile(
    r"FunctionCallingProcessor\(streaming\) inbound message: "
    r"correlation_id=([0-9a-fA-F-]+) message=(.*)$"
)

RUN_START_RE = re.compile(
    r"FunctionCallingProcessor\(streaming\): start correlation_id=([0-9a-fA-F-]+) "
    r"account=(\S+) agent=(\S+) session_id=(\S+) context_type=(\S*) max_iterations=(\d+)"
)

RUN_DONE_RE = re.compile(
    r"FunctionCallingProcessor\(streaming\): completed correlation_id=([0-9a-fA-F-]+) "
    r"agent=(\S+) session_id=(\S+) iterations=(\d+)"
)

TOOL_START_RE = re.compile(
    r"tool_execute_start correlation_id=([0-9a-fA-F-]+) tool=(\S+) call_id=(\S+)"
)

TOOL_DONE_RE = re.compile(
    r"tool_execute_done correlation_id=([0-9a-fA-F-]+) tool=(\S+) call_id=(\S+)"
)

RAW_TOOL_RE = re.compile(
    r"FunctionCallingProcessor\(streaming\): raw tool calls "
    r"correlation_id=([0-9a-fA-F-]+).*? iteration=(\d+) raw="
)

EXEC2_RE = re.compile(
    r" - execute_command2 account=(\S+) mode=(shell|process) cwd=(\S+) argv0=(\S+)"
)


@dataclass
class MessageRecord:
    timestamp: str
    correlation_id: str
    message: str


@dataclass
class ToolCallRecord:
    correlation_id: str
    call_id: str
    tool: str
    start_ts: str = ""
    done_ts: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    result_preview: str = ""
    exec2: str = ""


def timestamp_of(line: str) -> str:
    match = TIMESTAMP_RE.match(line)
    return match.group(1) if match else ""


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def resolve_log_files(log_file: str, all_files: bool) -> List[Path]:
    main = Path(log_file)
    if not all_files:
        return [main]
    rotated = sorted(main.parent.glob(main.name + ".*"), key=lambda p: p.stat().st_mtime)
    return rotated + [main]


def iter_lines(paths: List[Path]):
    for path in paths:
        if not path.is_file():
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line.rstrip("\n")


def parse_messages(paths: List[Path]) -> List[MessageRecord]:
    records = []
    for line in iter_lines(paths):
        match = INBOUND_RE.search(line)
        if not match:
            continue
        records.append(MessageRecord(timestamp_of(line), match.group(1), match.group(2)))
    return records


def parse_raw_entries(line: str) -> List[Dict[str, Any]]:
    marker = " raw="
    idx = line.find(marker)
    if idx == -1:
        return []
    start = idx + len(marker)
    end = line.find(" wrapped=[", start)
    if end == -1:
        end = len(line)
    chunk = line[start:end].strip()
    try:
        entries = ast.literal_eval(chunk)
    except (ValueError, SyntaxError):
        return []
    return entries if isinstance(entries, list) else []


def entry_args(entry: Dict[str, Any]) -> Dict[str, Any]:
    raw = entry.get("arguments", "") if isinstance(entry, dict) else ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_result_preview(line: str) -> str:
    marker = "result_preview='"
    idx = line.find(marker)
    if idx == -1:
        return ""
    payload = line[idx + len(marker):]
    if payload.endswith("'"):
        payload = payload[:-1]
    return payload


def parse_tools(paths: List[Path], correlation_ids: List[str]) -> Tuple[Dict, Dict, List[str]]:
    wanted = set(correlation_ids) if correlation_ids else set()
    runs: Dict[str, Dict[str, str]] = {}
    tool_calls: Dict[Tuple[str, str], ToolCallRecord] = {}
    cid_order: List[str] = []
    current_exec = None

    def seen(cid: str) -> None:
        if cid not in runs:
            runs[cid] = {
                "agent": "",
                "session_id": "",
                "max_iterations": "",
                "iterations": "",
                "start_ts": "",
                "done_ts": "",
            }
            cid_order.append(cid)

    for line in iter_lines(paths):
        exec2_match = EXEC2_RE.search(line)
        if exec2_match:
            match = exec2_match
            if match and current_exec is not None:
                cid, call_id = current_exec
                record = tool_calls.get((cid, call_id))
                if record:
                    record.exec2 = f"mode={match.group(2)} cwd={match.group(3)} argv0={match.group(4)}"
            continue

        cid_match = CORRELATION_RE.search(line)
        if not cid_match:
            continue
        cid = cid_match.group(1)
        if wanted and cid not in wanted:
            continue

        ts = timestamp_of(line)

        raw_match = RAW_TOOL_RE.search(line)
        if raw_match:
            seen(cid)
            for entry in parse_raw_entries(line):
                if not isinstance(entry, dict):
                    continue
                call_id = entry.get("id", "")
                tool = entry.get("name", "")
                if not call_id or not tool:
                    continue
                key = (cid, call_id)
                record = tool_calls.setdefault(key, ToolCallRecord(cid, call_id, tool))
                record.args = entry_args(entry)
            continue

        start_match = TOOL_START_RE.search(line)
        if start_match:
            seen(cid)
            key = (cid, start_match.group(3))
            record = tool_calls.setdefault(key, ToolCallRecord(cid, key[1], start_match.group(2)))
            record.start_ts = ts
            if record.tool == "execute_command":
                current_exec = key
            continue

        done_match = TOOL_DONE_RE.search(line)
        if done_match:
            seen(cid)
            key = (cid, done_match.group(3))
            record = tool_calls.setdefault(key, ToolCallRecord(cid, key[1], done_match.group(2)))
            record.done_ts = ts
            record.result_preview = extract_result_preview(line)
            continue

        run_start = RUN_START_RE.search(line)
        if run_start:
            seen(cid)
            runs[cid].update(
                {
                    "agent": run_start.group(3),
                    "session_id": run_start.group(4),
                    "max_iterations": run_start.group(6),
                    "start_ts": ts,
                }
            )
            continue

        run_done = RUN_DONE_RE.search(line)
        if run_done:
            seen(cid)
            runs[cid].update(
                {
                    "agent": run_done.group(2),
                    "session_id": run_done.group(3),
                    "iterations": run_done.group(4),
                    "done_ts": ts,
                }
            )
            continue

    return runs, tool_calls, cid_order


def format_exec_args(args: Dict[str, Any]) -> str:
    keys = ["mode", "external_root", "working_directory", "timeout_seconds", "script", "command"]
    parts = []
    for key in keys:
        value = args.get(key)
        if value not in (None, "", []):
            parts.append(f"{key}={value}")
    return " ".join(parts)


TOOL_EVENT_MARKERS = (
    "raw tool calls",
    "tool_execute_start",
    "tool_execute_done",
    "Tool execution failed",
)


def is_tool_line(line: str) -> bool:
    return any(marker in line for marker in TOOL_EVENT_MARKERS)


def line_matches_correlation(line: str, wanted: set) -> bool:
    match = CORRELATION_RE.search(line)
    return bool(match) and (not wanted or match.group(1) in wanted)


def line_matches_tool(line: str, tool: str) -> bool:
    return f"tool={tool}" in line or f"'name': '{tool}'" in line


def cmd_messages(args) -> int:
    paths = resolve_log_files(args.log_file, args.all)
    records = parse_messages(paths)[-args.last:]
    if not records:
        print("no user messages found")
        return 0
    for record in records:
        print(f"{record.timestamp}  {record.correlation_id}  {truncate(record.message, args.width)}")
    return 0


def cmd_tools(args) -> int:
    paths = resolve_log_files(args.log_file, args.all)
    runs, tool_calls, cid_order = parse_tools(paths, args.correlation_id)
    for cid in cid_order:
        run = runs.get(cid, {})
        print(f"correlation_id={cid}")
        if run.get("agent"):
            header = f"  agent={run['agent']} session_id={run['session_id']}"
            if run.get("max_iterations"):
                header += f" max_iterations={run['max_iterations']}"
            print(header)
        if run.get("start_ts"):
            print(f"  start    {run['start_ts']}")
        if run.get("done_ts"):
            print(f"  end      {run['done_ts']} iterations={run.get('iterations', '?')}")
        matches = [r for r in tool_calls.values() if r.correlation_id == cid]
        if args.tool:
            matches = [r for r in matches if r.tool == args.tool]
        if not matches:
            label = f"no {args.tool} tool calls found" if args.tool else "no tool calls found"
            print(f"  {label}")
            print()
            continue
        for record in matches:
            print(f"  [{record.start_ts or '?'}] {record.tool} {record.call_id}")
            if record.start_ts and record.done_ts:
                print(f"      start={record.start_ts} end={record.done_ts}")
            if record.tool == "execute_command" and record.args:
                print(f"      params: {format_exec_args(record.args)}")
            if record.exec2:
                print(f"      exec: {record.exec2}")
            if record.result_preview:
                print(f"      result: {truncate(record.result_preview, 200)}")
        print()
    return 0


def cmd_tools_raw(args) -> int:
    paths = resolve_log_files(args.log_file, args.all)
    wanted = set(args.correlation_id)
    found = False
    for line in iter_lines(paths):
        if not is_tool_line(line):
            continue
        if not line_matches_correlation(line, wanted):
            continue
        if args.tool and not line_matches_tool(line, args.tool):
            continue
        print(line)
        found = True
    if not found:
        print("no matching tool call lines found")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Lucy log messages and tool calls")
    sub = parser.add_subparsers(dest="command", required=True)

    messages = sub.add_parser("messages", help="list recent user messages with correlation ids")
    messages.add_argument("--last", "-n", type=int, default=10, help="number of messages (default: %(default)s)")
    messages.add_argument("--width", type=int, default=250, help="truncate message text to N chars (default: %(default)s)")
    messages.add_argument("--log-file", default=str(DEFAULT_LOG), help="log file path")
    messages.add_argument("--all", action="store_true", help="include rotated log files")

    tools = sub.add_parser("tools", help="show tool call records for correlation ids")
    tools.add_argument("correlation_id", nargs="+", help="one or more correlation ids")
    tools.add_argument("--tool", help="only show this tool name")
    tools.add_argument("--log-file", default=str(DEFAULT_LOG), help="log file path")
    tools.add_argument("--all", action="store_true", help="include rotated log files")
    tools.add_argument("--raw", action="store_true", help="print raw log lines instead of a summary")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "messages":
        return cmd_messages(args)
    if args.command == "tools":
        if args.raw:
            return cmd_tools_raw(args)
        return cmd_tools(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
