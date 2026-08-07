#!/usr/bin/env bash
# One-shot installer to run on a fresh Ubuntu VM (Oracle/Google free tier).
# Usage: bash crypto_collector/deploy/setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
USER_NAME="$(whoami)"
DEPLOY_DIR="$REPO_DIR/crypto_collector/deploy"

echo "==> repo: $REPO_DIR, user: $USER_NAME"

echo "==> installing OS packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

echo "==> python venv + deps"
cd "$REPO_DIR"
[[ -d .venv ]] || python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r crypto_collector/requirements.txt

if [[ ! -f crypto_collector/config.json ]]; then
  cp crypto_collector/config.example.json crypto_collector/config.json
  echo "==> wrote crypto_collector/config.json from the example (edit if needed)"
fi

if [[ ! -f "$DEPLOY_DIR/push.env" ]]; then
  echo "!! $DEPLOY_DIR/push.env is missing."
  echo "   cp crypto_collector/deploy/push.env.example crypto_collector/deploy/push.env"
  echo "   then paste a GitHub fine-grained PAT (Contents: read/write on this repo only) and chmod 600 it."
  echo "   Re-run this script after that."
  exit 1
fi
chmod 600 "$DEPLOY_DIR/push.env"

echo "==> installing systemd template units (instance = $USER_NAME)"
# Installed as real systemd templates (@.service): the %i inside each unit
# file is substituted automatically by systemd itself from the "@<name>"
# used in `systemctl enable ... @$USER_NAME...` below -- no manual sed needed,
# and the same template works for any username on any VM.
sudo cp "$DEPLOY_DIR/collector.service" /etc/systemd/system/collector@.service
sudo cp "$DEPLOY_DIR/push-snapshot.service" /etc/systemd/system/push-snapshot@.service
sudo cp "$DEPLOY_DIR/push-snapshot.timer" /etc/systemd/system/push-snapshot@.timer
sudo cp "$DEPLOY_DIR/healthcheck.service" /etc/systemd/system/healthcheck@.service
sudo cp "$DEPLOY_DIR/healthcheck.timer" /etc/systemd/system/healthcheck@.timer

sudo systemctl daemon-reload
sudo systemctl enable --now collector@$USER_NAME.service
sudo systemctl enable --now push-snapshot@$USER_NAME.timer
sudo systemctl enable --now healthcheck@$USER_NAME.timer

echo "==> done. Check status with:"
echo "    systemctl status collector@$USER_NAME.service"
echo "    journalctl -u collector@$USER_NAME.service -f"
