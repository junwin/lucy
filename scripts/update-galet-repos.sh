#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOS_ROOT="${1:-$SCRIPT_DIR}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

repos=(
  "galet"
  "galet-tools"
  "galet-memory"
  "galet-prompt-builder"
)

install_and_test() {
  local repo_name="$1"
  local repo_dir="$REPOS_ROOT/$repo_name"
  local venv_python="$repo_dir/.venv/bin/python"

  if [[ ! -d "$repo_dir/.git" ]]; then
    echo "ERROR: Git repository not found: $repo_dir" >&2
    return 1
  fi

  echo
  echo "===== $repo_name ====="

  git -C "$repo_dir" switch main
  git -C "$repo_dir" pull --ff-only origin main

  if [[ ! -x "$venv_python" ]]; then
    "$PYTHON_BIN" -m venv "$repo_dir/.venv"
  fi

  "$venv_python" -m pip install --upgrade pip

  case "$repo_name" in
    galet-memory|galet-prompt-builder)
      "$venv_python" -m pip install --upgrade "$repo_dir[test]"
      ;;
    *)
      "$venv_python" -m pip install --upgrade "$repo_dir" pytest
      ;;
  esac

  (
    cd "$repo_dir"
    "$venv_python" -m pytest
  )
}

echo "Repository root: $REPOS_ROOT"
echo "Update order: ${repos[*]}"

for repo in "${repos[@]}"; do
  install_and_test "$repo"
done

echo
echo "All Galet repositories updated and tested successfully."
