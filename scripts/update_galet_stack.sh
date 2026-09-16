#!/usr/bin/env bash
set -euo pipefail

# Update the local Galet-family repositories and reinstall them editable into
# Lucy's virtual environment in dependency order.
#
# Expected sibling layout by default:
#   <repos>/lucy
#   <repos>/galet
#   <repos>/galet-memory
#   <repos>/galet-tools
#   <repos>/galet-prompt-builder
#
# Usage:
#   ./scripts/update_galet_stack.sh
#   ./scripts/update_galet_stack.sh /path/to/repos

LUCY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_ROOT="${1:-$(dirname "$LUCY_ROOT")}"

if [[ -x "$LUCY_ROOT/.venv/bin/python" ]]; then
    PYTHON="$LUCY_ROOT/.venv/bin/python"
elif [[ -x "$LUCY_ROOT/venv/bin/python" ]]; then
    PYTHON="$LUCY_ROOT/venv/bin/python"
else
    echo "ERROR: Lucy virtual environment not found (.venv or venv)." >&2
    exit 1
fi

repos=(
    "galet"
    "galet-memory"
    "galet-tools"
    "galet-prompt-builder"
)

check_repo() {
    local repo="$1"
    local path="$REPOS_ROOT/$repo"

    if [[ ! -d "$path/.git" ]]; then
        echo "ERROR: repository not found: $path" >&2
        exit 1
    fi

    if [[ -n "$(git -C "$path" status --porcelain)" ]]; then
        echo "ERROR: $repo has uncommitted/untracked changes; refusing to switch/pull." >&2
        git -C "$path" status --short
        exit 1
    fi
}

update_repo() {
    local repo="$1"
    local path="$REPOS_ROOT/$repo"

    echo
    echo "=== Updating $repo ==="
    git -C "$path" fetch origin main
    git -C "$path" checkout main
    git -C "$path" pull --ff-only origin main
    echo "$repo -> $(git -C "$path" rev-parse --short HEAD)"
}

install_repo() {
    local repo="$1"
    local path="$REPOS_ROOT/$repo"

    echo
    echo "=== Installing $repo editable ==="
    "$PYTHON" -m pip install --no-deps -e "$path"
}

echo "Lucy root : $LUCY_ROOT"
echo "Repos root: $REPOS_ROOT"
echo "Python    : $PYTHON"
"$PYTHON" --version

for repo in "${repos[@]}"; do
    check_repo "$repo"
done

# Dependency order matters:
#   galet -> galet-memory -> galet-tools -> galet-prompt-builder
for repo in "${repos[@]}"; do
    update_repo "$repo"
    install_repo "$repo"
done

echo
echo "=== Verifying imports ==="
"$PYTHON" - <<'PY'
import galet
import galet_memory
import galet_tools
import galet_prompt_builder

for module in (galet, galet_memory, galet_tools, galet_prompt_builder):
    print(f"{module.__name__:22} {module.__file__}")
PY

echo
echo "=== pip check ==="
"$PYTHON" -m pip check

echo
echo "Galet stack update complete."
