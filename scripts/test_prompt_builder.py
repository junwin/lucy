#!/usr/bin/env python3
"""Test the prompt_builder endpoint."""
import json
import urllib.request

payload = {
    "query": "right but do you get information in the prompt we send to you about tasklists_manage added ",
    "agentName": "peace",
    "accountName": "junwin",
    "contextName": "lucyproject",
    "conversationId": "ecabac57-1777-4b5d-9072-0d28bd8e55c2"
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:5000/prompt_builder",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        print(body)
except Exception as e:
    print(f"Error: {e}")
