# Changelog

## v0.1.2

Cloud-VM / remote-Ollama boot without pretending the home NVR is up.

- Assistant `llm.py` / `vision.py` send `Authorization: Bearer` when
  `OLLAMA_API_KEY` or `SOVEREIGN_HOME_OLLAMA_API_KEY` is set (ollama.com or a
  protected tunnel). Local loopback with no key is unchanged.
- `OLLAMA_HOST` / `OLLAMA_MODEL` override config the same way
  `SOVEREIGN_HOME_OLLAMA_URL` / `SOVEREIGN_HOME_MODEL` already did. The
  sovereign-prefixed names still win.
- `./doctor.sh --offline` grades compile + scripts + templates and does **not**
  fail on missing Docker / Ollama / Frigate. Those stay live-only. Unittests
  stay a separate command (CI runs both).
- Live `./doctor.sh` probes the *configured* Ollama URL (not only
  `127.0.0.1:11434`) and passes a Bearer header when a key is set.
- CI runs `./doctor.sh --offline`.
- `./doctor.sh --no-nvr` requires live Ollama and treats Docker/Frigate as
  environment notes (Cloud VM assistant path).
- Privacy: `alerts.vision_caption` stays opt-in and off. Pointing `ollama_url`
  at a remote host and enabling vision sends snapshots to that host.

## v0.1.1

Convergence/packaging release.

- Docker hardening: `.dockerignore` excludes secrets and configs; `assistant/Dockerfile`
  copies only `.py` files so a local `config.json` can never be baked into an image layer.
- Single Compose path: `nvr/docker-compose.yml` removed; the root `docker-compose.yml`
  is canonical. Frigate image pinned to `0.17.1` (version proven on real hardware).
- Persistent Frigate config: volume mount changed from a single file to a directory
  (`nvr/config/`) so Frigate's sqlite db and generated state survive container recreation.
- Truthful `doctor.sh`: docker-daemon check added; Telegram failure now correctly
  increments the bad counter and causes a nonzero exit; `mktemp` replaces the fixed
  temp path; Ollama version note for the vision model added.
- `alert-watcher` container can now reach host Ollama on Linux (added
  `extra_hosts` + `SOVEREIGN_HOME_OLLAMA_URL` to match the other services).
- Telegram photo captions truncated to the correct 1024 UTF-16 unit limit.
- `telegram_bot.py` no longer logs full message text or full chat id on startup.
- Model default in `.env.example` updated to `qwen3.5:9b`.
- Frigate zone/motion-mask docs corrected to normalized 0–1 coordinates.
- `tailscale/README.md` example corrected to serve port 8971 (authenticated), not 5000.
- `SECURITY.md` added (trust boundaries, reporting path, home-grade disclaimer).
- CI extended: Compose config validation, YAML/JSON parse checks, model-default
  agreement assert, and archive-content guard against accidentally committed secrets.

## v0.1.0 - prepared

Initial public release candidate.

- Local assistant with memory, sitrep, Telegram notification, and two-way bot.
- Optional local vision-LLM snapshot captioning (default off; the image is sent
  only to local Ollama and never leaves the box; fail-soft).
- Frigate NVR starter with loopback-bound ports and authenticated remote UI path.
- Tailscale setup for private tailnet access.
- Backup-to-Pi script and docs.
- Reticulum node starter.
- Read-only hardening audit.
- Offline unit test suite and GitHub Actions CI.
- Top-level Docker Compose entrypoint for Frigate plus containerized assistant
  run targets.
