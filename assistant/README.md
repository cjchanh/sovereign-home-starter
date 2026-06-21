# assistant — local private AI, with memory + sitrep

A small chat assistant backed by a **local** model (Ollama). It remembers what you
tell it (a local JSONL file — nothing leaves the box) and can assemble a **sitrep**:
system health + recent camera events + your todos, summarized by the local model.

No third-party Python packages — just **Python 3.10+** and a running Ollama.

## Run
```bash
ollama pull qwen3.5:9b        # one time
cd assistant
python3 assistant.py          # chat: /remember, /todo, /sitrep, /quit
python3 sitrep.py             # print a sitrep on its own
```
`sitrep.py` runs from anywhere via its full path; for the chat REPL, running from
inside `assistant/` is simplest.

From the repo root, the Docker path is:

```bash
docker compose run --rm assistant
```

The container uses `SOVEREIGN_HOME_OLLAMA_URL`, `SOVEREIGN_HOME_NVR_URL`, and
`SOVEREIGN_HOME_MEMORY_PATH` from the Compose environment so it can talk to the
host Ollama process and the Frigate service correctly.

## Notifications (Telegram) — sitrep to your phone + camera alerts
1. In Telegram, message **@BotFather** → `/newbot` → copy the **bot token**.
2. Message your new bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy your **chat id**.
3. Put both in `assistant/config.json` under `notify` (it's gitignored, so the token
   never gets committed; cron reads it from there). You can also export
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

If they're unset, notify is a no-op — nothing crashes, you just get no push.

- `python3 sitrep.py --notify` — build the sitrep and push it to Telegram.
- `python3 alert_watcher.py` — push a Telegram alert for each new person/car event,
  with the Frigate snapshot photo attached. Falls back to a text alert if the photo
  can't be fetched. (One-shot; first run only seeds the baseline.)

## Two-way Telegram bot
`telegram_bot.py` is a long-running bot so you can **text the assistant from your
phone** and get replies — not just outbound push.

```bash
cd assistant
python3 telegram_bot.py [--config config.json]
```

Requires the same `notify.telegram_bot_token` + `notify.telegram_chat_id` in
`config.json`. With no credentials it prints a hint and exits 0.

**Security:** only your configured chat id gets responses. Messages from any other
chat are silently ignored.

Supported commands (same as the chat REPL):
- `/sitrep` — your daily brief
- `/remember <text>` — save a note
- `/todo <text>` — save a todo
- anything else → answered by the local model

**Retry backoff:** if the Telegram `getUpdates` call fails (network down, API error),
the bot retries with exponential backoff starting at 1 s, doubling on each consecutive
failure up to a cap of 60 s. A successful empty long-poll (normal Telegram timeout with
no new messages) is not counted as a failure — the backoff counter resets after any
successful poll.

### Run as a systemd service (optional)
```bash
cp telegram-bot.service.example ~/.config/systemd/user/telegram-bot.service
# edit ExecStart path in the unit file
systemctl --user daemon-reload
systemctl --user enable --now telegram-bot
```

## Cron (example)
```cron
# morning sitrep pushed to Telegram at 7am
0 7 * * *    cd /path/to/sovereign-home-starter/assistant && /usr/bin/python3 sitrep.py --notify >> "$HOME/sitrep.log" 2>&1
# person/car alerts: check Frigate every 2 minutes
*/2 * * * *  cd /path/to/sovereign-home-starter/assistant && /usr/bin/python3 alert_watcher.py >> "$HOME/alerts.log" 2>&1
```

## Picking a model for your box
Ollama models scale with RAM. Rough guide:
- **8 GB** → `qwen3.5:4b` (fast, light)
- **16 GB** → `qwen3.5:9b` (the default — good balance)
- **32 GB+** → `gemma4:12b` (sharper, slower)

Set it as `"model"` in `config.json`. `ollama list` shows what you've pulled.

**On CPU (no GPU), expect multi-second replies** — a 7B model is typically ~10–40s
per answer on a CPU-only box. That's normal, not broken. Use a smaller model for
snappier replies, or add a GPU. The alert watcher and sitrep don't wait on the model
unless you ask it to summarize.

## Config
Copy `config.example.json` to `config.json` (setup.sh does this) and edit the model,
memory path, and NVR URL. If `config.json` is missing, sensible defaults are used so
it still runs.

### New config knobs

**`sitrep.nvr_api_key`** (default `""`) — optional Bearer token for Frigate when it
sits behind a reverse proxy with auth enabled. Can also be set via the
`FRIGATE_API_KEY` environment variable (env wins over the config file). When unset,
all Frigate requests are sent without an `Authorization` header — identical to the
previous behaviour.

```json
"sitrep": {
  "nvr_url": "http://127.0.0.1:5000",
  "nvr_api_key": ""
}
```

Or in the shell:
```bash
export FRIGATE_API_KEY=your-token-here
```

**`alerts.cooldown_seconds`** (default `120`) — minimum gap in seconds between two
alerts for the **same camera**. If a second person/car event fires on camera A within
120 s of the first alert on camera A, it is suppressed (not delivered, not retried).
The high-water mark still advances past the suppressed event so it is not replayed on
the next cron run.

Alerts on **different** cameras are independent — a burst on "front" does not affect
"back".

```json
"alerts": {
  "cooldown_seconds": 120
}
```

Set to `0` to disable cooldown (deliver every event). Set higher (e.g. `300`) to
reduce noise on busy cameras.

**`alerts.vision_caption`** (default `false`) — optional local vision captioning for
camera alerts. When enabled, the Frigate snapshot for each person/car alert is sent
to a **local** Ollama vision model, which produces a one-line description (e.g.
"a person in a dark jacket at the front door"). That description is appended to the
alert caption before delivery.

The snapshot never leaves the box — it goes only to your local Ollama process. This
is the sovereignty-preserving path: on-device detection, on-device description, no
cloud.

**`alerts.vision_model`** (default `"qwen3-vl:8b"`) — the Ollama vision model to
use. Pull it once before enabling:

```bash
ollama pull qwen3-vl:8b
```

Any Ollama-compatible vision model works (e.g. `moondream:1.8b` for a tiny/fast
option, or `minicpm-v:8b`). Smaller models are faster; larger ones give better
descriptions. Check what is available with `ollama list`.

**`alerts.vision_timeout`** (default `30`) — max seconds for a single vision call
before it gives up and sends the plain alert. Lower it on slow hardware so a hung
model can't stall a run for long.

```json
"alerts": {
  "cooldown_seconds": 120,
  "vision_caption": true,
  "vision_model": "qwen3-vl:8b",
  "vision_timeout": 30
}
```

**Fail-soft guarantee:** if the vision model is slow, unavailable, or returns
garbage, `vision.describe_image` returns `None` and the plain alert is sent
unchanged. A failed or absent vision model never drops or blocks an alert, and
never delays it past `vision_timeout`. Delivery semantics are identical to the
no-vision path.

**Latency caveat (read this before enabling on CPU):** the vision call is
**serialized per alert** — one local inference (after the snapshot fetch, before
delivery). On a GPU this is ~1–5 s. On CPU a 7B vision model can take 30–90 s.
Two things follow:
- **Bursts multiply it.** The watcher processes all new events in one run, so *N*
  un-cooled alerts serialize *N* vision calls. At a 30 s timeout, several alerts in
  one run can exceed your cron interval (e.g. `*/2`). Keep `cooldown_seconds`
  non-zero, and/or use a small model (`moondream:1.8b`) when vision is on.
- **Tune the cap.** Lower `vision_timeout` to bound the worst case per alert.

If captions aren't worth the latency on your box, leave `vision_caption` at
`false` (the default). The fail-soft design means a slow model only adds latency —
it never breaks alerting.

## Files
- `assistant.py` — chat loop with memory + commands
- `telegram_bot.py` — two-way Telegram bot (text your assistant from your phone)
- `telegram-bot.service.example` — systemd user unit for running the bot
- `sitrep.py` — assembles the brief (system + cameras + todos); `--notify` pushes it
- `alert_watcher.py` — Frigate → Telegram person/car alerts, with snapshot photo (cron, one-shot)
- `frigate.py` — shared Frigate HTTP helper (auth header, fail-soft JSON/bytes fetch)
- `notify.py` — Telegram sender (zero deps, fail-soft); `send()` for text, `send_photo()` for images
- `vision.py` — optional local vision captioning via Ollama (zero deps, fail-soft)
- `memory.py` — append-only local memory store
- `llm.py` — minimal Ollama client (zero deps)
- `config.py` — config loader with defaults
