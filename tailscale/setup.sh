#!/usr/bin/env bash
# Wire this box into your tailnet and serve the local services privately.
# Everything stays tailnet-only — nothing is exposed to the public internet.
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "installing tailscale..."
  curl -fsSL https://tailscale.com/install.sh | sh
fi

echo "bringing up tailscale (this prints a login link)..."
sudo tailscale up

# Serve the Frigate camera UI privately over HTTPS on your tailnet.
# Reachable only by your own devices — never the public internet.
echo "serving Frigate UI on the tailnet..."
sudo tailscale serve --bg 5000

echo
echo "done. from any device signed into the same tailnet:"
echo "  tailscale status        # find this node's name"
echo "  open https://<node-name>.<your-tailnet>.ts.net/"
echo
echo "NOTE: 'serve' gives EVERY device/user on your tailnet access to the camera UI"
echo "      with no extra login. Keep your tailnet single-user, or restrict port 5000"
echo "      with a tailscale ACL grant. (Recent Frigate stable also has built-in auth.)"
echo
echo "NOTE: do NOT run 'tailscale funnel' unless you intend to expose this to the"
echo "      public internet. 'tailscale serve' keeps it private to your tailnet."
echo "      'sudo tailscale serve reset' stops serving."
