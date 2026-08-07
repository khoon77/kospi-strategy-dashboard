#!/usr/bin/env bash
# Pushes the latest price-bin snapshots to GitHub so the static GitHub Pages
# site stays close to live even though the VM never accepts inbound
# connections. Runs every few minutes from push-snapshot.timer.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/kospi-strategy-dashboard}"
BRANCH="${BRANCH:-main}"
FILES=("data/crypto_bins_recent.json" "data/crypto_bins_hourly.json" "data/crypto_status.json")

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

if git diff --quiet -- "${FILES[@]}" && git diff --cached --quiet -- "${FILES[@]}"; then
  exit 0  # nothing changed since last push, save the API call
fi

git add "${FILES[@]}"
git commit -m "crypto: refresh price-bin snapshots $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
git push "https://${GH_TOKEN}@github.com/khoon77/kospi-strategy-dashboard.git" "HEAD:$BRANCH" --quiet
