#!/usr/bin/env bash
# Back up this stack to another machine on your tailnet (e.g. your Raspberry Pi)
# over rsync+ssh. Mirrors the configs + assistant memory always, and the camera
# recordings only when you opt in (they're large). Idempotent — rsync copies only
# what changed.
#
# Usage:
#   ./backup.sh pi@raspberrypi                       # host from arg
#   TAILSCALE_BACKUP_HOST=pi@raspberrypi ./backup.sh # host from env
#   WITH_RECORDINGS=1 ./backup.sh pi@raspberrypi     # also mirror NVR video (big)
set -euo pipefail

host="${1:-${TAILSCALE_BACKUP_HOST:-}}"
if [ -z "$host" ]; then
  echo "usage: $0 <user@tailnet-host>   (e.g. pi@raspberrypi)"
  exit 2
fi
if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync not found — install it first (sudo apt install rsync)."
  exit 3
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base="sovereign-home-backup"

echo "preparing $host:~/$base ..."
ssh "$host" "mkdir -p ~/$base/state ~/$base/recordings"

# small state: configs + assistant memory (only the ones that exist)
srcs=()
for f in "$here/.env" "$here/nvr/config.yml" "$here/assistant/config.json"; do
  [ -f "$f" ] && srcs+=("$f")
done
[ -d "$HOME/.sovereign-home" ] && srcs+=("$HOME/.sovereign-home")
if [ "${#srcs[@]}" -gt 0 ]; then
  rsync -avz "${srcs[@]}" "$host:~/$base/state/"
else
  echo "  (no state files yet — run setup first)"
fi

# recordings: large, opt-in
if [ "${WITH_RECORDINGS:-0}" = "1" ] && [ -d "$here/nvr/storage" ]; then
  echo "mirroring NVR recordings (this can be large)..."
  rsync -avz "$here/nvr/storage/" "$host:~/$base/recordings/"
fi

echo "backup complete -> $host:~/$base"
