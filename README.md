# sovereign-home-starter

A **local-first, private, zero-subscription** home stack you stand up on one Linux
box and reach from your phone. Drop this repo into Claude Code and it'll walk you
through setup.

Four pieces, all running on **your** hardware — nothing phones home:

1. **Private AI assistant** — a local model (Ollama) with memory. Remembers what you
   tell it, answers day-to-day questions, and builds you a **sitrep**.
2. **Daily sitrep, on your phone** — system health + recent camera events + your todos,
   summarized by the local model and pushed to **Telegram**. Cron it for a morning brief.
3. **Local AI camera NVR + alerts** — Frigate records your RTSP cameras (Tapo *and*
   Reolink) and does person/vehicle detection on-device, with **Telegram alerts** when
   someone's at the gate. No 8-camera hub limit, no subscription.
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
2. **Cameras:** `cd nvr && docker compose up -d` → Frigate at http://localhost:5000
3. **Model:** `ollama pull qwen2.5:7b`
4. **Assistant:** `cd assistant && python3 assistant.py`
5. **Phone delivery:** add your Telegram bot token to `assistant/config.json`, then
   `python3 sitrep.py --notify` (sitrep) and cron `alert_watcher.py` (camera alerts) —
   see `assistant/README.md`.
6. **Remote access:** `./tailscale/setup.sh` → reach it from your phone, tailnet-only
7. **Backup:** `./backup/backup.sh pi@your-pi` · **Harden:** see `docs/HARDENING.md`

Each folder has its own README with detail. Using Claude Code? Just open this repo
and ask it to walk you through — the `CLAUDE.md` here tells it how.

## What's where
| Folder        | What it does                                                   |
|---------------|----------------------------------------------------------------|
| `assistant/`  | Local chat assistant, memory, sitrep, Telegram notify + alerts |
| `nvr/`        | Frigate camera NVR (docker-compose + config + RTSP checker)    |
| `tailscale/`  | Wire the box into your tailnet, serve services privately       |
| `backup/`     | rsync the stack to your Pi over Tailscale                      |
| `docs/`       | Box-hardening checklist (home-grade)                           |
| `lint/`       | Optional mildoc-lint for compliance docs                       |

## Privacy + safety
- Everything runs locally. The assistant uses a local model; detection is on-device.
- Secrets (`.env`, `nvr/config.yml`, `assistant/config.json`) are gitignored — never
  committed.
- Services are exposed to your **tailnet only**, never the public internet.

MIT licensed. Yours to fork, change, and run.
