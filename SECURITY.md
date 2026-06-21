# Security

## Reporting a vulnerability

Use GitHub's **private vulnerability reporting** feature (Security tab →
"Report a vulnerability") so the report stays confidential until a fix is ready.
If you prefer, open a public issue with a minimal repro and mark it with the
`security` label — this repo is a home starter, not a production service, so a
low-key report is fine.

Please include: what you found, how to reproduce it, and which component is
affected (assistant, Frigate config, Docker wiring, Tailscale setup, etc.).

## Trust boundaries

| What | Where it runs | Leaves the box? |
|------|--------------|----------------|
| AI assistant + model | Local (Ollama) | No |
| Camera detection + recordings | Local (Frigate) | No |
| Notes / sitrep data | Local file (`~/.sovereign-home/`) | No |
| Telegram sitrep / alerts / bot | Optional, opt-in | Yes — via Telegram's servers, like any Telegram message |
| Remote UI (Frigate) | Tailscale only, authenticated port 8971 | No — tailnet only |

- The core is fully local. Leave Telegram off for a 100% local setup.
- Remote access goes through your **tailnet** (Tailscale), not the public internet.
  The Frigate UI is served on the **authenticated** port 8971, not the unauthenticated
  port 5000. Port 5000 stays bound to localhost only.
- Secrets (`.env`, `nvr/config/config.yml`, `assistant/config.json`) are gitignored
  and `chmod 600`d by `setup.sh`.

## Disclaimer

This is a personal home-lab starter, not audited or hardened software. Use the
hardening checklist in `docs/HARDENING.md` and the audit in `security/audit.sh`
as a starting point, not a guarantee. Run it on hardware you control, and keep
your tailnet ACLs tight.
