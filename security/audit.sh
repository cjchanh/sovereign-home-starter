#!/usr/bin/env bash
# Read-only security audit — reports PASS/FAIL/WARN/SKIP against the items in
# docs/HARDENING.md. Never modifies anything. Never locks you out.
# Exits 0 if everything passes (WARN/SKIP are non-fatal); exits 1 if any check FAILs.
#
#   ./security/audit.sh          (some checks read more with: sudo ./security/audit.sh)
set -uo pipefail   # NOT -e: run every check, report all, then decide exit code

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0; warn=0; skip=0

_pass() { echo "[PASS] $1"; pass=$((pass + 1)); }
_fail() { echo "[FAIL] $1"; fail=$((fail + 1)); }
_warn() { echo "[WARN] $1"; warn=$((warn + 1)); }
_skip() { echo "[SKIP] $1"; skip=$((skip + 1)); }
_lower() { tr '[:upper:]' '[:lower:]'; }   # portable lowercase (no bash 4 needed)

echo "== sovereign-home security audit =="
echo

# -- 1. SSH key-only ----------------------------------------------------------
echo "1. SSH sshd_config"
sshd_cfg="/etc/ssh/sshd_config"
if [ ! -r "$sshd_cfg" ]; then
  _skip "sshd_config not readable (not Linux, no SSH server, or needs sudo)"
else
  # last active (non-commented) directive wins in sshd_config
  pw_val="$(grep -E '^\s*PasswordAuthentication\s+' "$sshd_cfg" | awk '{print $2}' | tail -1 | _lower)"
  root_val="$(grep -E '^\s*PermitRootLogin\s+' "$sshd_cfg" | awk '{print $2}' | tail -1 | _lower)"

  if [ "$pw_val" = "no" ]; then
    _pass "PasswordAuthentication no"
  elif [ -z "$pw_val" ]; then
    _fail "PasswordAuthentication not set — default may allow passwords; add 'PasswordAuthentication no' to $sshd_cfg"
  else
    _fail "PasswordAuthentication is '$pw_val' — set to 'no' in $sshd_cfg"
  fi

  if [ "$root_val" = "no" ]; then
    _pass "PermitRootLogin no"
  elif [ -z "$root_val" ]; then
    _fail "PermitRootLogin not set — default allows root login; add 'PermitRootLogin no' to $sshd_cfg"
  else
    _fail "PermitRootLogin is '$root_val' — set to 'no' in $sshd_cfg"
  fi
fi
echo

# -- 2. ufw -------------------------------------------------------------------
echo "2. ufw firewall"
if ! command -v ufw >/dev/null 2>&1; then
  _skip "ufw not installed (not Debian/Ubuntu, or not yet set up)"
else
  # -n: never prompt for a password. If we can't read status, SKIP (can't-check)
  # rather than FAIL (which would wrongly look like the firewall is off).
  ufw_out="$(sudo -n ufw status verbose 2>/dev/null || true)"
  if [ -z "$ufw_out" ]; then
    _skip "ufw needs root to read status — re-run with: sudo ./security/audit.sh"
  else
    if echo "$ufw_out" | grep -q "Status: active"; then
      _pass "ufw active"
    else
      _fail "ufw not active — run: sudo ufw enable"
    fi
    if echo "$ufw_out" | grep -q "Default: deny (incoming)"; then
      _pass "ufw default deny incoming"
    else
      _fail "ufw default is not deny incoming — run: sudo ufw default deny incoming"
    fi
  fi
fi
echo

# -- 3. fail2ban --------------------------------------------------------------
echo "3. fail2ban"
if ! command -v fail2ban-client >/dev/null 2>&1 && ! pgrep fail2ban >/dev/null 2>&1; then
  _skip "fail2ban not installed — optional; install with: sudo apt install fail2ban"
else
  if systemctl is-active --quiet fail2ban 2>/dev/null || pgrep -x fail2ban >/dev/null 2>&1; then
    _pass "fail2ban running"
  else
    _fail "fail2ban installed but not running — run: sudo systemctl enable --now fail2ban"
  fi
fi
echo

# -- 4. unattended-upgrades ---------------------------------------------------
echo "4. unattended-upgrades (auto-patch)"
if ! command -v apt-get >/dev/null 2>&1; then
  _skip "not Debian/Ubuntu — check your distro's equivalent auto-update mechanism"
else
  if dpkg -l unattended-upgrades 2>/dev/null | grep -q "^ii"; then
    _pass "unattended-upgrades installed"
  else
    _fail "unattended-upgrades not installed — run: sudo apt install unattended-upgrades"
  fi
fi
echo

# -- 5. Secret file permissions -----------------------------------------------
echo "5. Secret file permissions (must be 600)"
secret_files=(
  "$here/.env"
  "$here/nvr/config/config.yml"
  "$here/assistant/config.json"
)
any_secret_found=0
for f in "${secret_files[@]}"; do
  if [ ! -e "$f" ]; then
    _skip "$(basename "$f") not present yet (run setup first)"
    continue
  fi
  any_secret_found=1
  mode="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%OLp' "$f" 2>/dev/null || echo "unknown")"
  if [ "$mode" = "600" ]; then
    _pass "$(basename "$f") is 600"
  else
    _fail "$(basename "$f") is $mode — run: chmod 600 $f"
  fi
done
if [ "$any_secret_found" -eq 0 ]; then
  echo "       (no secret files exist yet — check again after setup)"
fi
echo

# -- 6. Frigate ports bound to loopback ---------------------------------------
echo "6. Frigate port bindings (docker-compose.yml)"
compose_file="$here/docker-compose.yml"
if [ ! -f "$compose_file" ]; then
  _skip "docker-compose.yml not found"
else
  # published port lines (- "5000:5000") that are NOT prefixed with 127.0.0.1
  bad_ports="$(grep -E '^\s*-\s+"?[0-9]' "$compose_file" | grep -v '127\.0\.0\.1' || true)"
  if [ -z "$bad_ports" ]; then
    _pass "all published ports are bound to 127.0.0.1"
  else
    _fail "port(s) not bound to 127.0.0.1 — this exposes services to the LAN:"
    echo "$bad_ports" | sed 's/^/         /'
    echo "       Fix: prefix each port with '127.0.0.1:', e.g. '127.0.0.1:5000:5000'"
  fi
fi
echo

# -- 7. Tailscale funnel ------------------------------------------------------
echo "7. Tailscale funnel (should be off)"
if ! command -v tailscale >/dev/null 2>&1; then
  _skip "tailscale not installed"
else
  funnel_out="$(tailscale funnel status 2>/dev/null || true)"
  # An active funnel prints the public https:// URL(s) it serves.
  if echo "$funnel_out" | grep -qE 'https://'; then
    _fail "tailscale funnel appears active — this exposes services to the PUBLIC internet"
    echo "$funnel_out" | sed 's/^/         /'
    echo "       Fix: sudo tailscale funnel reset"
  else
    _pass "tailscale funnel not active"
  fi
fi
echo

# -- 8. Listeners on 0.0.0.0/:: (review, not a failure) -----------------------
echo "8. Listeners on 0.0.0.0 / ::"
if ! command -v ss >/dev/null 2>&1; then
  _skip "ss not found — install iproute2 or check with: netstat -tulpn"
else
  exposed="$(ss -tulpn 2>/dev/null | grep -E '0\.0\.0\.0:|:::' | grep -v '127\.' | grep -v '::1' || true)"
  if [ -z "$exposed" ]; then
    _pass "no world-reachable listeners found"
  else
    # SSH on :22 is normal and wanted, so this is a WARN to review, not a FAIL.
    _warn "services bound to 0.0.0.0 or :: — review (SSH on :22 is expected; bind the rest to 127.0.0.1):"
    echo "$exposed" | sed 's/^/         /'
  fi
fi
echo

# -- 9. Docker group membership -----------------------------------------------
echo "9. Docker group (root-equivalent)"
if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx "docker"; then
  _warn "current user is in the 'docker' group — root-equivalent on a shared box"
  echo "       If unintended: sudo gpasswd -d \$USER docker (use sudo docker, or rootless Docker)"
else
  _pass "current user is not in the docker group"
fi
echo

# -- Summary ------------------------------------------------------------------
total=$((pass + fail + warn + skip))
echo "== summary =="
echo "  PASS: $pass  FAIL: $fail  WARN: $warn  SKIP: $skip  (of $total checks)"
echo
if [ "$fail" -gt 0 ]; then
  echo "Action required: $fail check(s) failed. See [FAIL] lines above."
  exit 1
else
  echo "No failures. Review any [WARN] lines above."
fi
