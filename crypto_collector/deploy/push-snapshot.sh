#!/usr/bin/env bash
# Pushes the latest crypto_profile.json snapshot to GitHub so the static
# GitHub Pages site stays close to live even though the VM never accepts
# inbound connections. Runs every few minutes from push-snapshot.timer.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/kospi-strategy-dashboard}"
BRANCH="${BRANCH:-main}"
FILE="data/crypto_profile.json"

# GH_TOKEN comes from an EnvironmentFile with 600 perms (see push-snapshot.service).
# Never stored in git config / remote URL history, only used for this one push.
if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is not set; refusing to push." >&2
  exit 1
fi

cd "$REPO_DIR"

# Pull first in case something else (KOSPI collect.yml, a manual commit) moved main.
git fetch origin "$BRANCH" --quiet
git merge --ff-only "origin/$BRANCH" --quiet || {
  echo "Fast-forward failed, skipping this cycle to avoid a messy merge." >&2
  exit 0
}

if git diff --quiet -- "$FILE" && git diff --cached --quiet -- "$FILE"; then
  exit 0  # nothing changed since last push, save the API call
fi

git add "$FILE"
git commit -m "crypto: refresh live snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
git push "https://${GH_TOKEN}@github.com/khoon77/kospi-strategy-dashboard.git" "HEAD:$BRANCH" --quiet
