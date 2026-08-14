#!/usr/bin/env python3
"""Test the prompt_builder/metrics endpoint.

Posts a query to /prompt_builder/metrics and pretty-prints the JSON
response. The endpoint returns the per-section token breakdown computed
by PromptBuilder after history selection (system_session, context_text,
obsidian_notes, digest_embeddings, chat_history, overflow_digest,
current_user_message, total_without_handlers), plus the tool handler
schema set (handler_schema_tokens, tool_count, handlers, and the enriched
breakdown keys tool_handler_schemas / total_with_handlers).

CLI overrides:
    sys.argv[1] = query text
    sys.argv[2] = agentName (default "peace")
    sys.argv[3] = accountName (default "junwin")
"""
import json
import sys
import urllib.error
import urllib.request

DEFAULT_QUERY = (
    "Show me the token breakdown for this prompt: how many tokens go to the "
    "system/session messages, context text, obsidian notes, digest embeddings, "
    "chat history, overflow digest, and the current user message?"
)

query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
agent_name = sys.argv[2] if len(sys.argv) > 2 else "peace"
account_name = sys.argv[3] if len(sys.argv) > 3 else "junwin"

payload = {
    "query": query,
    "agentName": agent_name,
    "accountName": account_name,
    "contextName": "lucyproject",
    "conversationId": "",
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:5000/prompt_builder/metrics",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        try:
            print(json.dumps(json.loads(body), indent=2))
        except (ValueError, TypeError):
            print(body)
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8", errors="replace")
    try:
        detail = json.dumps(json.loads(error_body), indent=2)
    except (ValueError, TypeError):
        detail = error_body
    print(f"HTTP {e.code}: {e.reason}")
    if detail:
        print(detail)
except urllib.error.URLError as e:
    print(f"Error: {e.reason}")
except Exception as e:
    print(f"Error: {e}")
