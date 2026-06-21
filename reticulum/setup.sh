#!/usr/bin/env bash
# Set up a Reticulum (RNS) node on this machine.
# - Installs the rns package via pip.
# - Seeds ~/.reticulum/config from config.example if no config exists yet.
#   NEVER overwrites an existing config — your node identity lives there.
# - Prints how to start the daemon and check status.
#
#   ./reticulum/setup.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rns_config_dir="$HOME/.reticulum"
rns_config="$rns_config_dir/config"

# ── prerequisites ─────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found — install Python 3.8+ first."
  exit 1
fi

if ! command -v pip3 >/dev/null 2>&1 && ! python3 -m pip --version >/dev/null 2>&1; then
  echo "pip not found — install pip first: sudo apt install python3-pip"
  exit 1
fi

# ── install rns ───────────────────────────────────────────────────────────────
# Modern Debian/Ubuntu (PEP 668) block a system-wide pip install, so prefer pipx
# (isolated, gives the rnsd/rnstatus CLIs), then fall back to pip and --user.
echo "installing rns (Reticulum Network Stack)..."
if command -v pipx >/dev/null 2>&1; then
  # Don't swallow a real failure: install, or (if already present) upgrade. If
  # BOTH fail, fall through to the error path below instead of `|| true`.
  pipx install rns >/dev/null 2>&1 || pipx upgrade rns >/dev/null 2>&1 || {
    echo "pipx could not install rns — try: pipx install rns"
    exit 1
  }
elif python3 -m pip install --quiet --upgrade rns >/dev/null 2>&1; then
  :
elif python3 -m pip install --quiet --user --upgrade rns >/dev/null 2>&1; then
  :
else
  echo "could not install rns automatically (modern distros block system pip — PEP 668)."
  echo "do one of:"
  echo "  sudo apt install pipx && pipx install rns          # recommended"
  echo "  python3 -m pip install --user --break-system-packages rns"
  exit 1
fi

echo
echo "rns installed. optional: install nomadnet for a terminal browser/messenger:"
echo "  pip3 install nomadnet"

# ── seed config (only if none exists) ─────────────────────────────────────────
echo
if [ -f "$rns_config" ]; then
  echo "~/.reticulum/config already exists — not overwriting. Your node identity is in there."
else
  mkdir -p "$rns_config_dir"
  cp "$here/config.example" "$rns_config"
  echo "seeded ~/.reticulum/config from config.example."
  echo "edit it to enable the interfaces you want (TCP is on by default)."
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo
echo "start the Reticulum daemon:"
echo "  rnsd                      # foreground"
echo "  rnsd --daemon             # background"
echo
echo "check status:"
echo "  rnstatus                  # shows interfaces, announce rate, destinations"
echo
echo "install the systemd service (optional, runs as your user on boot):"
echo "  cp $here/rnsd.service.example ~/.config/systemd/user/rnsd.service"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now rnsd"
echo
echo "NOTE: ~/.reticulum/ holds your node's private identity."
echo "      Keep it private. Do not commit it."
