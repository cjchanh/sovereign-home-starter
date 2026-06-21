#!/usr/bin/env bash
# Health check — does each piece ACTUALLY work? Pokes the real endpoints (not a
# status flag), reports per-component, exits 1 if a required check fails. Run it
# after setup, or any time something feels off.
#
#   ./doctor.sh
set -uo pipefail   # deliberately NOT -e: run every check and report, don't abort early

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bad=0
pass() { echo "  [ok]   $1"; }
warn() { echo "  [--]   $1"; }
fail() { echo "  [FAIL] $1"; bad=$((bad + 1)); }

echo "== sovereign-home doctor =="

# docker daemon
if docker info >/dev/null 2>&1; then
  pass "docker daemon running"
else
  fail "docker daemon not running — start Docker"
fi

# python
if command -v python3 >/dev/null 2>&1; then pass "python3 ($(python3 -V 2>&1))"; else fail "python3 missing"; fi

# the model the assistant is configured to use
model="$(python3 - "$here" <<'PY' 2>/dev/null || echo "qwen3.5:9b"
import sys
sys.path.insert(0, sys.argv[1] + "/assistant")
import config
print(config.load_config(sys.argv[1] + "/assistant/config.json")["model"])
PY
)"

# ollama reachable + model pulled
_ollama_tmp="$(mktemp)"
if curl -fsS http://127.0.0.1:11434/api/tags -o "$_ollama_tmp" 2>/dev/null; then
  pass "ollama reachable (:11434)"
  if python3 - "$model" "$_ollama_tmp" <<'PY' 2>/dev/null
import json, sys
want = sys.argv[1]
tmpf = sys.argv[2]
# Match the EXACT configured model, tag and all. Ollama reports "qwen3.5:9b";
# a default ":latest" config is matched against "<name>:latest" or a bare "<name>".
names = {m.get("name", "") for m in json.load(open(tmpf)).get("models", [])}
bare = {n.split(":")[0] for n in names}
ok = want in names or (":" not in want and want in bare)
sys.exit(0 if ok else 1)
PY
  then
    pass "assistant model present ($model)"
  else
    fail "model '$model' not pulled — run: ollama pull $model"
  fi
else
  fail "ollama not reachable on :11434 — run: ollama serve"
fi
rm -f "$_ollama_tmp"

warn "vision model qwen3-vl:8b requires Ollama >= 0.12.7 — run 'ollama --version' to confirm if you use vision captioning"

# frigate UI up. Use 127.0.0.1 (IPv4), NOT localhost: Docker binds the port on
# 127.0.0.1 only, but localhost can resolve to ::1 (IPv6) first -> false FAIL.
if curl -fsS http://127.0.0.1:5000/api/version -o /dev/null 2>/dev/null; then
  pass "frigate up (:5000)"
else
  fail "frigate not reachable on :5000 — docker compose up -d frigate"
fi

# tailscale up
if command -v tailscale >/dev/null 2>&1 && tailscale status >/dev/null 2>&1; then
  pass "tailscale up"
else
  warn "tailscale not up (optional) — ./tailscale/setup.sh for remote access"
fi

# telegram — only if configured; sends a real test message
_tg_rc=0
python3 - "$here" <<'PY' 2>/dev/null
import sys
here = sys.argv[1]
sys.path.insert(0, here + "/assistant")
import config, notify
cfg = config.load_config(here + "/assistant/config.json")
tok, chat = notify._creds(cfg)
if not (tok and chat):
    print("  [--]   telegram not configured (optional) — see assistant/README.md")
    sys.exit(0)
if notify.send("sovereign-home doctor: notifications are wired.", cfg):
    print("  [ok]   telegram test message sent")
    sys.exit(0)
else:
    print("  [FAIL] telegram token set but send failed — check token/chat id")
    sys.exit(2)
PY
_tg_rc=$?
if [ "$_tg_rc" -eq 2 ]; then
  bad=$((bad + 1))
fi

echo
if [ "$bad" -eq 0 ]; then
  echo "all required checks passed."
else
  echo "$bad required check(s) need attention (see [FAIL] above)."
  exit 1
fi
