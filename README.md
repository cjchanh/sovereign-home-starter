# sovereign-home-starter

A **local-first, private, zero-subscription** home stack you stand up on one Linux
box and reach from your phone. Drop this repo into Claude Code and it'll walk you
through setup.

Four pieces, all running on **your** hardware — nothing phones home:

1. **Private AI assistant** — a local model (Ollama) with memory. Remembers what you
   tell it, answers day-to-day questions, and builds you a **sitrep**.
2. **Daily sitrep** — system health + recent camera events + your todos, summarized
   by the local model. Cron it for a morning brief.
3. **Local AI camera NVR** — Frigate records your RTSP cameras (Tapo included) and
   does person/vehicle detection on-device. No 8-camera hub limit, no subscription.
4. **Tailscale wiring** — reach the assistant and cameras from anywhere, **privately**
   (tailnet-only, never public).

Plus optional **mildoc-lint** to keep your docs/configs clean.

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

## Quick start
```bash
git clone <this-repo> sovereign-home-starter
cd sovereign-home-starter
./setup.sh                       # checks prereqs, seeds config files
```
Then:
1. Edit `.env` and `nvr/config.yml` with your camera IPs + RTSP credentials.
2. **Cameras:** `cd nvr && docker compose up -d` → Frigate at http://localhost:5000
3. **Model:** `ollama pull qwen2.5:7b`
4. **Assistant:** `cd assistant && python3 assistant.py`
5. **Sitrep:** `cd assistant && python3 sitrep.py` (add to cron for a daily brief)
6. **Remote access:** `./tailscale/setup.sh` → reach it from your phone, tailnet-only

Each folder has its own README with detail. Using Claude Code? Just open this repo
and ask it to walk you through — the `CLAUDE.md` here tells it how.

## What's where
| Folder        | What it does                                             |
|---------------|----------------------------------------------------------|
| `assistant/`  | Local chat assistant + memory + sitrep (pure Python)     |
| `nvr/`        | Frigate camera NVR (docker-compose + config)             |
| `tailscale/`  | Wire the box into your tailnet, serve services privately |
| `lint/`       | Optional mildoc-lint for your docs/configs               |

## Privacy + safety
- Everything runs locally. The assistant uses a local model; detection is on-device.
- Secrets (`.env`, `nvr/config.yml`, `assistant/config.json`) are gitignored — never
  committed.
- Services are exposed to your **tailnet only**, never the public internet.

MIT licensed. Yours to fork, change, and run.
