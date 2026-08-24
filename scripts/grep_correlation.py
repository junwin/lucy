#!/usr/bin/env python3
"""Show execute_command tool calls for a correlation id from the log file."""
import argparse
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "my_log_file.log"


def extract_payload(line):
    marker = "result_preview='"
    idx = line.find(marker)
    if idx == -1:
        return None
    payload = line[idx + len(marker):].rstrip("\n")
    if payload.endswith("'"):
        payload = payload[:-1]
    return payload


def extract_field(payload, field):
    marker = '"%s": "' % field
    idx = payload.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    end = start
    while end < len(payload):
        if payload[end] == '\\':
            end += 1
            continue
        if payload[end] == '"' and (end == start or payload[end - 1] != '\\'):
            break
        end += 1
    raw = payload[start:end]
    out = []
    i = 0
    while i < len(raw):
        if raw[i] == '\\' and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return ''.join(out)


def main():
    parser = argparse.ArgumentParser(description="Show execute_command tool calls for a correlation id")
    parser.add_argument("correlation_id", help="correlation id to search for")
    parser.add_argument("--log-file", default=str(DEFAULT_LOG), help="path to log file")
    args = parser.parse_args()

    count = 0
    with open(args.log_file, "r", encoding="utf-8") as fh:
        for line in fh:
            if args.correlation_id not in line:
                continue
            if "tool=execute_command" not in line or "result_preview=" not in line:
                continue
            payload = extract_payload(line)
            if payload is None:
                continue
            external_root = extract_field(payload, "external_root")
            command = extract_field(payload, "command")
            print(line.rstrip("\n"))
            print(f"external_root: {external_root}")
            print(f"command: {command}")
            print()
            count += 1
    print(f"{count} execute_command result(s) for correlation_id={args.correlation_id}")


if __name__ == "__main__":
    main()
