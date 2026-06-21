# sovereign-home-starter

A **local-first, private, zero-subscription** home stack you stand up on one Linux
box and reach from your phone. Drop this repo into Claude Code and it'll walk you
through setup.

Four pieces, all running on **your** hardware. The core — assistant, model,
camera detection, recordings — is fully local and never leaves the box. The **one
exception** is opt-in: if you enable the Telegram features (sitrep-to-phone,
camera alerts, the two-way bot), those messages route through Telegram's servers
like any Telegram message. Leave Telegram off and it's 100% local; the alerts also
work over your tailnet without it.

1. **Private AI assistant** — a local model (Ollama) with memory. Chat in the terminal
   **or text it from your phone** (two-way Telegram bot); it remembers what you tell it
   and builds you a **sitrep**.
2. **Daily sitrep, on your phone** — system health + recent camera events + your todos,
   summarized by the local model and pushed to **Telegram**. Cron it for a morning brief.
3. **Local AI camera NVR + alerts** — Frigate records your RTSP cameras (Tapo *and*
   Reolink) and does person/vehicle detection on-device, with **Telegram alerts (plus the
   snapshot photo)** when someone's at the gate. No 8-camera hub limit, no subscription.
4. **Tailscale wiring** — reach the assistant and cameras from anywhere, **privately**
   (tailnet-only, never public).

Plus a **box-hardening checklist**, a **backup-to-your-Pi** script, and optional
**mildoc-lint** for compliance docs.

```
+-----------------------------------------------------------+
|  your Linux box (everything local)                        |
|                                                           |
|   Tapo / RTSP cams ---> Frigate NVR ----+                 |
|                          (detect+rec)   |                 |
|                                         v                 |
|   local model (Ollama) ---> assistant + sitrep            |
|                                         |                 |
+-----------------------------------------|-----------------+
                                          v
                            Tailscale (tailnet-only)
                                          v
                          your phone / laptop, anywhere
```

## Prerequisites
- A Linux box with **Docker** and **Python 3.10+**
- **Ollama** (https://ollama.com) for the local assistant model
- A **Tailscale** account (you've got this)
- One or more **RTSP cameras** (Tapo, Reolink, etc.)
- *Optional:* a **Telegram** account (sitrep + alerts to your phone), `ffmpeg` (the
  camera checker), `rsync` (backup to your Pi)

## Quick start
```bash
git clone <this-repo> sovereign-home-starter
cd sovereign-home-starter
./setup.sh                       # checks prereqs, seeds config files
```
Then:
1. Edit `.env` and `nvr/config.yml` with your camera IPs + RTSP credentials.
   (Test a camera first: `nvr/check-camera.sh 'rtsp://user:pass@IP:554/stream2'`.)
2. **Cameras:** `docker compose up -d frigate` -> Frigate auth UI at
   http://localhost:8971 (internal API remains loopback-only at http://localhost:5000)
3. **Model:** `ollama pull qwen2.5:7b`
4. **Assistant:** `cd assistant && python3 assistant.py`
5. **Phone delivery:** add your Telegram bot token to `assistant/config.json`, then
   `python3 sitrep.py --notify` (sitrep) and cron `alert_watcher.py` (camera alerts) —
   see `assistant/README.md`. (Per-camera alert cooldown, default 120s, and optional
   Frigate proxy-auth `nvr_api_key` are also set in `assistant/config.json`.)
6. **Remote access:** `./tailscale/setup.sh` → reach it from your phone, tailnet-only
7. **Backup:** `./backup/backup.sh pi@your-pi` · **Harden:** see `docs/HARDENING.md`

Each folder has its own README with detail. Using Claude Code? Just open this repo
and ask it to walk you through — the `CLAUDE.md` here tells it how.

## Docker Compose path
The top-level compose file is the easiest way to run the service layer from the
repo root:

```bash
./setup.sh
docker compose up -d frigate                  # camera NVR
docker compose run --rm assistant             # interactive local assistant
docker compose --profile phone up -d telegram-bot
docker compose --profile jobs run --rm alert-watcher
```

Compose uses the same `.env` that `setup.sh` creates. The assistant container
talks to Ollama on the host via `host.docker.internal` and talks to Frigate over
the private Compose network.

**Two things to know:**
- **Run `./setup.sh` first** so `nvr/config.yml` exists before `docker compose up`
  (a missing bind source would otherwise be created as an empty directory).
- For the containers to reach Ollama on the host, start Ollama bound to all
  interfaces: `OLLAMA_HOST=0.0.0.0 ollama serve` (the default 127.0.0.1 isn't
  reachable from inside a container).

## Verify it works
- `./doctor.sh` — pokes your **live** services (Ollama + model, Frigate, Tailscale,
  and a real Telegram test message) and tells you exactly what's wired and what isn't.
- `python3 -m unittest discover -s tests` — offline logic tests (no services needed).
- `docker compose config` — validates the top-level Compose stack.

## What's where
| Folder        | What it does                                                   |
|---------------|----------------------------------------------------------------|
| `assistant/`  | Chat + two-way Telegram bot, memory, sitrep, notify + alerts    |
| `nvr/`        | Frigate camera NVR (compose + config + RTSP checker + TUNING.md)|
| `tailscale/`  | Wire the box into your tailnet, serve services privately       |
| `backup/`     | rsync the stack to your Pi over Tailscale                      |
| `docs/`       | Box-hardening checklist (home-grade)                           |
| `security/`   | Read-only hardening audit (`./security/audit.sh`)              |
| `reticulum/`  | Optional sovereign mesh node (Reticulum/RNS) starter           |
| `tests/`      | Offline smoke tests (`python3 -m unittest discover -s tests`)   |
| `lint/`       | Optional mildoc-lint for compliance docs                       |

(`doctor.sh` and `setup.sh` live at the root.)

## Privacy + safety
- The core runs locally: a local model, on-device detection, recordings on your disk.
- **The one thing that leaves the box** is opt-in Telegram (sitrep/alerts/bot) — those
  messages transit Telegram's servers. Disable Telegram for a fully-local setup; the
  alerts still work over your tailnet.
- Secrets (`.env`, `nvr/config.yml`, `assistant/config.json`) are gitignored, and
  `setup.sh` `chmod 600`s them; your assistant notes (`~/.sovereign-home/`) are owner-only.
- Remote access is **tailnet only**, and via Frigate's *authenticated* port (8971) —
  never the unauthenticated :5000, which stays bound to localhost.

Apache-2.0 licensed. Yours to fork, change, and run.
