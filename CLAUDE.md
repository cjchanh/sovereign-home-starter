# CLAUDE.md — sovereign-home-starter

This repo sets up a **local-first, private, zero-subscription** home stack on one
Linux box: a private AI assistant with memory + daily sitrep, a local AI camera
NVR (Frigate), and Tailscale wiring so it's reachable from your phone — privately.

You (the agent) are helping the owner stand this up. Be concrete and hands-on.

## Ground rules
- **Local-only.** Nothing here should phone home or require a paid subscription.
  The assistant runs on a local model (Ollama). Detection runs on-device (Frigate).
- **Never expose services to the public internet.** Use `tailscale serve` (tailnet
  only), never `tailscale funnel`. Keep ports bound to localhost/tailnet.
- **Never commit secrets.** `.env`, `assistant/config.json`, and `nvr/config.yml`
  hold credentials and are gitignored. Help the owner fill them; don't print them back.
- **Don't run destructive commands** without explaining them first.

## Setup order (help the owner through these)
1. `./setup.sh` — checks prerequisites, seeds config files.
2. Fill `.env` and `nvr/config.yml` with camera IPs + RTSP credentials.
   (Tapo: app -> camera -> Advanced Settings -> Camera Account, then enable RTSP.)
3. `cd nvr && docker compose up -d` — Frigate at http://localhost:5000
4. `ollama pull qwen2.5:7b` — the local assistant model.
5. `cd assistant && python3 assistant.py` — talk to the assistant.
6. `python3 assistant/sitrep.py` — generate a brief; add to cron for a daily one.
7. `./tailscale/setup.sh` — reach it all from your phone, tailnet-only.
8. Optional: add a Telegram bot token to `assistant/config.json` for phone delivery —
   `sitrep.py --notify` (sitrep) and cron `alert_watcher.py` (person/car alerts).
9. Optional: `./backup/backup.sh pi@host` to mirror to the Pi; `docs/HARDENING.md` to harden.

## Layout
- `assistant/` — local chat assistant, sitrep, Telegram notify + camera alert watcher
- `nvr/` — Frigate docker-compose + config + RTSP checker (local camera AI)
- `tailscale/` — wire the box into your tailnet and serve services privately
- `backup/` — rsync the stack to a tailnet host (e.g. the Pi)
- `docs/` — home-grade box-hardening checklist
- `security/` — read-only hardening audit that scores docs/HARDENING.md
- `reticulum/` — optional sovereign mesh (Reticulum/RNS) node starter
- `tests/` — offline smoke tests (`python3 -m unittest discover -s tests`)
- `doctor.sh` — health check that pokes the live services (Ollama/Frigate/Tailscale/Telegram)
- `lint/` — optional: compliance-doc linting with mildoc-lint

Keep it simple. This is one person's private home stack, not a production fleet.
