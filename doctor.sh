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

# python
if command -v python3 >/dev/null 2>&1; then pass "python3 ($(python3 -V 2>&1))"; else fail "python3 missing"; fi

# the model the assistant is configured to use
model="$(python3 - "$here" <<'PY' 2>/dev/null || echo "qwen2.5:7b"
import sys
sys.path.insert(0, sys.argv[1] + "/assistant")
import config
print(config.load_config(sys.argv[1] + "/assistant/config.json")["model"])
PY
)"

# ollama reachable + model pulled
if curl -fsS http://localhost:11434/api/tags -o /tmp/_sh_ollama.json 2>/dev/null; then
  pass "ollama reachable (:11434)"
  if python3 - "$model" <<'PY' 2>/dev/null
import json, sys
want = sys.argv[1]
# Match the EXACT configured model, tag and all. Ollama reports "qwen2.5:7b";
# a default ":latest" config is matched against "<name>:latest" or a bare "<name>".
names = {m.get("name", "") for m in json.load(open("/tmp/_sh_ollama.json")).get("models", [])}
bare = {n.split(":")[0] for n in names}
ok = want in names or (":" not in want and want in bare)
sys.exit(0 if ok else 1)
PY
  then pass "assistant model present ($model)"; else fail "model '$model' not pulled — run: ollama pull $model"; fi
else
  fail "ollama not reachable on :11434 — run: ollama serve"
fi

# frigate UI up
if curl -fsS http://localhost:5000/api/version -o /dev/null 2>/dev/null; then
  pass "frigate up (:5000)"
else
  fail "frigate not reachable on :5000 — cd nvr && docker compose up -d"
fi

# tailscale up
if command -v tailscale >/dev/null 2>&1 && tailscale status >/dev/null 2>&1; then
  pass "tailscale up"
else
  warn "tailscale not up (optional) — ./tailscale/setup.sh for remote access"
fi

# telegram — only if configured; sends a real test message
python3 - "$here" <<'PY'
import sys
here = sys.argv[1]
sys.path.insert(0, here + "/assistant")
import config, notify
cfg = config.load_config(here + "/assistant/config.json")
tok, chat = notify._creds(cfg)
if not (tok and chat):
    print("  [--]   telegram not configured (optional) — see assistant/README.md")
elif notify.send("✅ sovereign-home doctor: notifications are wired.", cfg):
    print("  [ok]   telegram test message sent")
else:
    print("  [FAIL] telegram token set but send failed — check token/chat id")
PY

echo
if [ "$bad" -eq 0 ]; then
  echo "all required checks passed."
else
  echo "$bad required check(s) need attention (see [FAIL] above)."
  exit 1
fi
