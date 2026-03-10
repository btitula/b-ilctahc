#!/usr/bin/env bash
# Scans commits not yet on the remote for secrets using gitleaks detect.
# Called as a pre-push local hook via pre-commit.
set -euo pipefail

CONFIG="$(git rev-parse --show-toplevel)/.gitleaks.toml"
REMOTE_BRANCH="origin/main"

if git rev-parse --verify "$REMOTE_BRANCH" &>/dev/null; then
    RANGE="${REMOTE_BRANCH}..HEAD"
else
    # No remote ref yet (first push) — scan all commits
    RANGE="HEAD"
fi

COUNT=$(git log --oneline $RANGE 2>/dev/null | wc -l | tr -d ' ')
if [[ "$COUNT" -eq 0 ]]; then
    echo "  No new commits to scan."
    exit 0
fi

echo "  Scanning $COUNT commit(s) ($RANGE) for secrets..."
gitleaks detect --source=. --log-opts="$RANGE" --config="$CONFIG" -v
