#!/usr/bin/env bash
set -euo pipefail

# Demo curl script for Lucy Flask API (app.py)
# Usage:
#   ./scripts/demo_endpoints.sh
#   BASE_URL=http://localhost:5000 ./scripts/demo_endpoints.sh
#   CONVERSATION_ID=... ./scripts/demo_endpoints.sh

BASE_URL="${BASE_URL:-http://localhost:5000}"
AGENT_NAME="${AGENT_NAME:-lucy}"
ACCOUNT_NAME="${ACCOUNT_NAME:-junwin}"
CONTEXT_NAME="${CONTEXT_NAME:-lucyproject}"
CONVERSATION_ID="${CONVERSATION_ID:-4ca5f862-813f-4f9c-a11c-4810909aa544}"

# If you run the server with SSL, use:
#   BASE_URL=https://localhost:5000
# and add CURL_INSECURE=-k
CURL_INSECURE="${CURL_INSECURE:-}"

hdr_json=(-H "Content-Type: application/json")

say() { printf "\n==> %s\n" "$*"; }

say "GET /swagger.json"
curl -sS ${CURL_INSECURE} "$BASE_URL/swagger.json" | head -n 40

auth_payload=$(cat <<JSON
{
  "agentName": "$AGENT_NAME",
  "accountName": "$ACCOUNT_NAME",
  "contextName": "$CONTEXT_NAME",
  "conversationId": "$CONVERSATION_ID"
}
JSON
)

say "GET /context/names"
curl -sS ${CURL_INSECURE} "$BASE_URL/context/names"

say "GET /agents"
curl -sS ${CURL_INSECURE} "$BASE_URL/agents"

say "POST /prompt_builder"
curl -sS ${CURL_INSECURE} -X POST "$BASE_URL/prompt_builder" "${hdr_json[@]}" \
  -d "$(jq -nc --arg q 'test prompt builder' \
              --arg agentName "$AGENT_NAME" \
              --arg accountName "$ACCOUNT_NAME" \
              --arg contextName "$CONTEXT_NAME" \
              --arg conversationId "$CONVERSATION_ID" \
              '{query:$q, agentName:$agentName, accountName:$accountName, contextName:$contextName, conversationId:$conversationId}')"

say "POST /ask"
curl -sS ${CURL_INSECURE} -X POST "$BASE_URL/ask" "${hdr_json[@]}" \
  -d "$(jq -nc --arg q 'hello' \
              --arg agentName "$AGENT_NAME" \
              --arg accountName "$ACCOUNT_NAME" \
              --arg contextName "$CONTEXT_NAME" \
              --arg conversationId "$CONVERSATION_ID" \
              '{query:$q, agentName:$agentName, accountName:$accountName, contextName:$contextName, conversationId:$conversationId}')"

say "POST /chats (create)"
create_chat_resp=$(curl -sS ${CURL_INSECURE} -X POST "$BASE_URL/chats" "${hdr_json[@]}" \
  -d "$(jq -nc --arg agentName "$AGENT_NAME" \
              --arg accountName "$ACCOUNT_NAME" \
              --arg contextName "$CONTEXT_NAME" \
              '{agentName:$agentName, accountName:$accountName, contextName:$contextName}')")

echo "$create_chat_resp"

# Try to extract session_id from common shapes
SESSION_ID=$(echo "$create_chat_resp" | jq -r '.session_id // .sessionId // .id // empty')
if [[ -z "${SESSION_ID}" || "${SESSION_ID}" == "null" ]]; then
  say "Could not detect session_id from /chats response; skipping session-specific endpoints"
  exit 0
fi

say "GET /chats (list)"
curl -sS ${CURL_INSECURE} "$BASE_URL/chats"

say "GET /chats/$SESSION_ID"
curl -sS ${CURL_INSECURE} "$BASE_URL/chats/$SESSION_ID"

say "POST /chats/$SESSION_ID/messages"
curl -sS ${CURL_INSECURE} -X POST "$BASE_URL/chats/$SESSION_ID/messages" "${hdr_json[@]}" \
  -d "$(jq -nc --arg role 'user' --arg content 'hello from demo script' '{role:$role, content:$content}')"

say "PATCH /chats/$SESSION_ID (rename/update)"
curl -sS ${CURL_INSECURE} -X PATCH "$BASE_URL/chats/$SESSION_ID" "${hdr_json[@]}" \
  -d "$(jq -nc --arg title 'Demo chat title' '{title:$title}')"

say "POST /documents/search"
curl -sS ${CURL_INSECURE} -X POST "$BASE_URL/documents/search" "${hdr_json[@]}" \
  -d "$(jq -nc --arg q 'test' --arg accountName "$ACCOUNT_NAME" --arg contextName "$CONTEXT_NAME" '{query:$q, accountName:$accountName, contextName:$contextName}')"

say "DELETE /chats/$SESSION_ID"
curl -sS ${CURL_INSECURE} -X DELETE "$BASE_URL/chats/$SESSION_ID"

echo
say "Done"
