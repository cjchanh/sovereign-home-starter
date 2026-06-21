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
Run the commands from inside the `assistant/` folder so the modules import cleanly.

## Daily sitrep via cron (example: 7am)
```cron
0 7 * * *  cd /path/to/sovereign-home-starter/assistant && /usr/bin/python3 sitrep.py >> "$HOME/sitrep.log" 2>&1
```

## Config
Copy `config.example.json` to `config.json` (setup.sh does this) and edit the model,
memory path, and NVR URL. If `config.json` is missing, sensible defaults are used so
it still runs.

## Files
- `assistant.py` — chat loop with memory + commands
- `sitrep.py` — assembles the brief (system + cameras + todos)
- `memory.py` — append-only local memory store
- `llm.py` — minimal Ollama client (zero deps)
- `config.py` — config loader with defaults
