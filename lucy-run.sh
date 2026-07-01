#!/usr/bin/env bash
# Lucy CLI launcher — use from anywhere.
# Usage:
#   lucy-run server        Start the Flask API server (foreground)
#   lucy-run repl          Interactive REPL
#   lucy-run ask "query"   Single query, prints result, exits

set -e

LUCY_HOME="/home/junwin/src/repos/lucy"
VENV="$LUCY_HOME/venv"

cd "$LUCY_HOME" || exit 1
source "$VENV/bin/activate"

case "${1:-}" in
  server)
    echo "Starting Lucy Flask server on 0.0.0.0:5000 (SSL)..."
    python app.py
    ;;
  repl)
    shift
    python main.py --agentName lucy --accountName junwin --friendlyName "cli-$(date +%F)" "$@"
    ;;
  ask)
    shift
    if [ -z "$1" ]; then
      echo "Usage: lucy-run ask \"your question\""
      exit 1
    fi
    python main.py --agentName lucy --accountName junwin --query "$1"
    ;;
  *)
    echo "Usage: lucy-run {server|repl|ask <query>}"
    exit 1
    ;;
esac
