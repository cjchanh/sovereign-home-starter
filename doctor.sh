#!/usr/bin/env bash
# Health check. Live mode pokes real endpoints. --offline grades product
# logic only and treats missing Docker/Ollama/Frigate as environment notes.
#
#   ./doctor.sh
#   ./doctor.sh --offline
set -uo pipefail   # deliberately NOT -e: run every check and report, don't abort early

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
offline=0
for a in "$@"; do
  case "$a" in
    --offline) offline=1 ;;
    -h|--help)
      echo "Usage: ./doctor.sh [--offline]"
      echo "  (default) probe live Docker / Ollama / Frigate / optional Telegram"
      echo "  --offline  product logic only (compile, scripts, templates)"
      exit 0
      ;;
    *)
      echo "unknown argument: $a" >&2
      echo "Usage: ./doctor.sh [--offline]" >&2
      exit 2
      ;;
  esac
done

bad=0
env_notes=0
pass() { echo "  [ok]   $1"; }
warn() { echo "  [--]   $1"; }
fail() { echo "  [FAIL] $1"; bad=$((bad + 1)); }
envnote() { echo "  [env]  $1"; env_notes=$((env_notes + 1)); }

if [ "$offline" -eq 1 ]; then
  echo "== sovereign-home doctor (offline) =="
else
  echo "== sovereign-home doctor =="
fi

# python
if command -v python3 >/dev/null 2>&1; then pass "python3 ($(python3 -V 2>&1))"; else fail "python3 missing"; fi

if [ "$offline" -eq 1 ]; then
  if python3 -m py_compile "$here"/assistant/*.py; then
    pass "assistant/*.py compiles"
  else
    fail "assistant/*.py failed py_compile"
  fi
  _bash_bad=0
  while IFS= read -r -d '' s; do
    if ! bash -n "$s"; then
      fail "bash -n $s"
      _bash_bad=1
    fi
  done < <(find "$here" -name '*.sh' -print0)
  if [ "$_bash_bad" -eq 0 ]; then
    pass "shell scripts bash -n"
  fi
  for t in \
    "$here/.env.example" \
    "$here/assistant/config.example.json" \
    "$here/nvr/config.example.yml" \
    "$here/docker-compose.yml"
  do
    if [ -s "$t" ]; then
      pass "template $(basename "$t")"
    else
      fail "missing or empty template: $t"
    fi
  done
  envnote "docker / ollama / frigate / telegram not probed (--offline)"
  echo
  if [ "$bad" -eq 0 ]; then
    echo "offline product checks passed. $env_notes env note(s). live services not probed."
    exit 0
  fi
  echo "$bad product check(s) failed (see [FAIL] above)."
  exit 1
fi

# docker daemon
if docker info >/dev/null 2>&1; then
  pass "docker daemon running"
else
  fail "docker daemon not running — start Docker"
fi

# the model the assistant is configured to use (honors OLLAMA_HOST / OLLAMA_MODEL)
model="$(python3 - "$here" <<'PY' 2>/dev/null || echo "qwen3.5:9b"
import sys
sys.path.insert(0, sys.argv[1] + "/assistant")
import config
print(config.load_config(sys.argv[1] + "/assistant/config.json")["model"])
PY
)"
ollama_url="$(python3 - "$here" <<'PY' 2>/dev/null || echo "http://127.0.0.1:11434"
import sys
sys.path.insert(0, sys.argv[1] + "/assistant")
import config
print(config.load_config(sys.argv[1] + "/assistant/config.json")["ollama_url"])
PY
)"

# ollama reachable + model pulled (configured URL, with Bearer if a key is set)
_ollama_tmp="$(mktemp)"
_curl_auth=()
if [ -n "${SOVEREIGN_HOME_OLLAMA_API_KEY:-}" ]; then
  _curl_auth=(-H "Authorization: Bearer ${SOVEREIGN_HOME_OLLAMA_API_KEY}")
elif [ -n "${OLLAMA_API_KEY:-}" ]; then
  _curl_auth=(-H "Authorization: Bearer ${OLLAMA_API_KEY}")
fi
if curl -fsS "${_curl_auth[@]}" "${ollama_url%/}/api/tags" -o "$_ollama_tmp" 2>/dev/null; then
  pass "ollama reachable ($ollama_url)"
  if python3 - "$model" "$_ollama_tmp" <<'PY' 2>/dev/null
import json, sys
want = sys.argv[1]
tmpf = sys.argv[2]
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
  fail "ollama not reachable at $ollama_url — run: ollama serve (or set OLLAMA_HOST + OLLAMA_API_KEY)"
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
