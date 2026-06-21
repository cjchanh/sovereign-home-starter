#!/usr/bin/env bash
# sovereign-home-starter — guided local setup. Safe + idempotent: checks
# prerequisites and seeds example config files into place. Nothing destructive,
# never overwrites an existing real config.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "== sovereign-home-starter setup =="

# 1. prerequisites ----------------------------------------------------------
need() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ok:      $1"
  else
    echo "  MISSING: $1 — $2"
  fi
}
echo "checking prerequisites..."
need python3   "install Python 3.10+"
need docker    "install Docker (for the camera NVR)"
need tailscale "run ./tailscale/setup.sh to install"
need ollama    "install from https://ollama.com (for the local assistant model)"

# 2. seed config files (never overwrite an existing real config) ------------
seed() {
  if [ -f "$2" ]; then
    echo "  keep:    $2 (already exists)"
  else
    cp "$1" "$2"
    echo "  created: $2"
  fi
}
echo "seeding config files..."
seed "$here/.env.example"                 "$here/.env"
seed "$here/assistant/config.example.json" "$here/assistant/config.json"
seed "$here/nvr/config.example.yml"        "$here/nvr/config.yml"

cat <<'NEXT'

next steps (see README.md and each folder's README for detail):
  1. edit .env and nvr/config.yml with your camera IPs + credentials
  2. cameras:   cd nvr && docker compose up -d        # Frigate at http://localhost:5000
  3. model:     ollama pull qwen2.5:7b
  4. assistant: cd assistant && python3 assistant.py
  5. sitrep:    cd assistant && python3 sitrep.py     # add to cron for a daily brief
  6. remote:    ./tailscale/setup.sh                  # reach it from your phone, tailnet-only
NEXT
