# security — read-only home hardening audit

A lightweight scanner that checks the nine items in `docs/HARDENING.md` and
reports each as `[PASS]`, `[FAIL]`, or `[SKIP]` (skip when a tool isn't
installed or a file doesn't exist yet). It is **strictly read-only** — it
never modifies configs, never touches a service, never locks you out.

## Run it

```bash
./security/audit.sh
```

Exits 0 if every active check passes; exits 1 if anything fails. Safe to
run at any time, including before you've finished setup (missing files and
absent tools just show as SKIP).

## What it checks

| # | Item |
|---|------|
| 1 | SSH — `PasswordAuthentication no` + `PermitRootLogin no` in sshd_config |
| 2 | ufw — installed, active, default deny incoming |
| 3 | fail2ban — service running |
| 4 | unattended-upgrades — installed (Debian/Ubuntu only) |
| 5 | Secret files (`.env`, `nvr/config.yml`, `assistant/config.json`) — mode 600 |
| 6 | Frigate ports all bound to `127.0.0.1` in `nvr/docker-compose.yml` |
| 7 | Tailscale funnel — not active (funnel = public internet exposure) |
| 8 | Listeners — nothing unexpected bound to `0.0.0.0` or `::` |
| 9 | Docker group — current user is not in it (it's root-equivalent) |

Each FAIL line includes a one-line remediation command.

## Honest limits

This is not a CIS benchmark or a STIG pass. It is the 80/20 for a home
Linux box whose services are tailnet-only. It catches the most common
self-inflicted exposures. For a real hardening audit, use `lynis` or a
proper CIS-CAT scanner.
