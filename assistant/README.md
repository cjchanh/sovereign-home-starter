# assistant — local private AI, with memory + sitrep

A small chat assistant backed by a **local** model (Ollama). It remembers what you
tell it (a local JSONL file — nothing leaves the box) and can assemble a **sitrep**:
system health + recent camera events + your todos, summarized by the local model.

No third-party Python packages — just **Python 3.10+** and a running Ollama.

## Run
```bash
ollama pull qwen2.5:7b        # one time
cd assistant
python3 assistant.py          # chat: /remember, /todo, /sitrep, /quit
python3 sitrep.py             # print a sitrep on its own
```
`sitrep.py` runs from anywhere via its full path; for the chat REPL, running from
inside `assistant/` is simplest.

## Notifications (Telegram) — sitrep to your phone + camera alerts
1. In Telegram, message **@BotFather** → `/newbot` → copy the **bot token**.
2. Message your new bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy your **chat id**.
3. Put both in `assistant/config.json` under `notify` (it's gitignored, so the token
   never gets committed; cron reads it from there). You can also export
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

If they're unset, notify is a no-op — nothing crashes, you just get no push.

- `python3 sitrep.py --notify` — build the sitrep and push it to Telegram.
- `python3 alert_watcher.py` — push a Telegram alert for each new person/car event
  (one-shot; first run only seeds the baseline, so no blast of old events).

## Cron (example)
```cron
# morning sitrep pushed to Telegram at 7am
0 7 * * *    cd /path/to/sovereign-home-starter/assistant && /usr/bin/python3 sitrep.py --notify >> "$HOME/sitrep.log" 2>&1
# person/car alerts: check Frigate every 2 minutes
*/2 * * * *  cd /path/to/sovereign-home-starter/assistant && /usr/bin/python3 alert_watcher.py >> "$HOME/alerts.log" 2>&1
```

## Picking a model for your box
Ollama models scale with RAM. Rough guide:
- **8 GB** → `qwen2.5:3b` (fast, light)
- **16 GB** → `qwen2.5:7b` (the default — good balance)
- **32 GB+** → `qwen2.5:14b` (sharper, slower)

Set it as `"model"` in `config.json`. `ollama list` shows what you've pulled.

## Config
Copy `config.example.json` to `config.json` (setup.sh does this) and edit the model,
memory path, and NVR URL. If `config.json` is missing, sensible defaults are used so
it still runs.

## Files
- `assistant.py` — chat loop with memory + commands
- `sitrep.py` — assembles the brief (system + cameras + todos); `--notify` pushes it
- `alert_watcher.py` — Frigate → Telegram person/car alerts (cron, one-shot)
- `notify.py` — Telegram sender (zero deps, fail-soft)
- `memory.py` — append-only local memory store
- `llm.py` — minimal Ollama client (zero deps)
- `config.py` — config loader with defaults
