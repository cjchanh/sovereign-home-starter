# Hardening this box (home-grade)

You build STIG servers — this isn't that. It's the 80/20 for a home Linux box whose
services are exposed only to your tailnet. Cherry-pick what fits; you'll recognize
all of it.

The starter already does two of these for you: Frigate's ports are bound to
`127.0.0.1` (not the LAN), and secrets live in gitignored files. The rest is yours
to apply.

## 1. SSH — key-only
In `/etc/ssh/sshd_config`:
```
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
```
`sudo systemctl restart ssh`

## 2. Firewall — default deny, trust only the tailnet
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0      # trust the tailnet interface
sudo ufw allow 22/tcp                # SSH (tighten to LAN/tailnet if you can)
sudo ufw enable
```
Frigate's ports are already `127.0.0.1`-bound, so they're not LAN-reachable
regardless of ufw.

## 3. Auto-patch
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

## 4. fail2ban (SSH brute-force shield)
```bash
sudo apt install fail2ban
sudo systemctl enable --now fail2ban
```

## 5. Docker
- Don't add your user to the `docker` group on a box you share — it's root-equivalent.
  Use `sudo`, or run rootless Docker.
- Keep images current: `cd nvr && docker compose pull && docker compose up -d`.

## 6. Secrets at rest
```bash
chmod 600 .env nvr/config.yml assistant/config.json
```
They're gitignored already — keep them that way.

## 7. Tailscale
- `serve`, never `funnel`. Single-user tailnet, or restrict port 5000 with an ACL grant.

## Quick audit
```bash
ss -tulpn              # what's listening — confirm nothing unexpected on 0.0.0.0
sudo ufw status verbose
tailscale status
```

This is a home checklist, not a benchmark. If you want a real CIS/STIG pass on this
box later, that's a different (bigger) job — say the word.
