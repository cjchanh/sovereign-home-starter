#!/usr/bin/env bash
# sovereign-home-starter — guided local setup. Safe + idempotent: checks
# prerequisites and seeds example config files into place. Nothing destructive,
# never overwrites an existing real config.
set -euo pipefail
umask 077   # any file we create is owner-only — no world/group-readable window for secrets

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
# 'docker compose' is a plugin — command -v can't see a subcommand, so check it directly.
if docker compose version >/dev/null 2>&1; then
  echo "  ok:      docker compose"
else
  echo "  MISSING: docker compose plugin — install the docker-compose-plugin package"
fi
need tailscale "run ./tailscale/setup.sh to install"
need ollama    "install from https://ollama.com (for the local assistant model)"

# 2. seed config files (never overwrite an existing real config) ------------
seed() {
  if [ ! -f "$1" ]; then
    echo "  ERROR:   missing template $1 (skipping — others still seed)"
    return 0   # non-fatal: never abort seeding the remaining configs under set -e
  fi
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

# Lock down the secret-bearing files so they aren't world/group readable. The
# audit (security/audit.sh) CHECKS for 600 — this is what actually SETS it.
for s in "$here/.env" "$here/assistant/config.json" "$here/nvr/config.yml"; do
  [ -f "$s" ] && chmod 600 "$s" && echo "  chmod 600: $s"
done

cat <<'NEXT'

next steps (see README.md and each folder's README for detail):
  1. edit .env and nvr/config.yml with your camera IPs + credentials
  2. cameras:   docker compose up -d frigate          # Frigate auth UI at http://127.0.0.1:8971
  3. model:     ollama pull qwen3.5:9b
  4. assistant: cd assistant && python3 assistant.py  # or: docker compose run --rm assistant
  5. sitrep:    cd assistant && python3 sitrep.py     # add to cron for a daily brief
  6. remote:    ./tailscale/setup.sh                  # reach it from your phone, tailnet-only
  7. alerts:    add a Telegram bot token to assistant/config.json, then
                python3 assistant/sitrep.py --notify  # + cron assistant/alert_watcher.py
  8. backup:    ./backup/backup.sh pi@your-pi         # mirror to your tailnet Pi
  9. harden:    see docs/HARDENING.md
  --- verify ---
  ./doctor.sh                                         # check the live services
  python3 -m unittest discover -s tests               # offline logic tests
  docker compose config                               # compose syntax / wiring check
NEXT
