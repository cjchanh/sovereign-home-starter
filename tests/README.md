# tests — prove it works on your box

Stdlib `unittest`, zero third-party deps. Network calls are mocked, so these run
offline and verify the **logic** (memory, config fail-soft, Telegram truncation,
the alert watcher's paging / retry-hold / corrupt-state handling).

```bash
python3 -m unittest discover -s tests
# or:
python3 tests/test_assistant.py
```

These check the code. To check your **live services** (Ollama, Frigate, Tailscale,
Telegram), run `./doctor.sh` from the repo root.
