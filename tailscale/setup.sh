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
# We serve 8971 — Frigate's AUTHENTICATED interface (it asks for a login). Do NOT
# serve 5000: that is the UNAUTHENTICATED port and would hand every tailnet device
# the camera UI with no login. (Frigate generates admin creds on first start; see
# its logs / the Frigate auth docs.)
echo "serving Frigate's authenticated UI (8971) on the tailnet..."
sudo tailscale serve --bg 8971

echo
echo "done. from any device signed into the same tailnet:"
echo "  tailscale status        # find this node's name"
echo "  open https://<node-name>.<your-tailnet>.ts.net/"
echo
echo "NOTE: 8971 is Frigate's authenticated UI — log in with the admin creds Frigate"
echo "      printed in its logs on first start. Keep your tailnet trusted too; a"
echo "      tailscale ACL grant can further restrict who reaches this node."
echo
echo "NOTE: do NOT run 'tailscale funnel' unless you intend to expose this to the"
echo "      public internet. 'tailscale serve' keeps it private to your tailnet."
echo "      'sudo tailscale serve reset' stops serving."
