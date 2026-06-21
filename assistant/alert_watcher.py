#!/usr/bin/env python3
"""Watch Frigate for new person/car events and push a Telegram alert for each.

One-shot by design: each run alerts on events newer than the previous run, then
records a high-water mark to a small state file. Run it from cron every minute or
two — no long-running daemon to babysit.

Failure posture (it's a security alerter, so it errs toward NOT dropping alerts):
- A send failure (Telegram/network down) does NOT advance the mark past the unsent
  event, so the next run retries it. Duplicate alert > dropped alert.
- A burst of >100 events is paged through (Frigate caps each response and orders
  newest-first, so we walk backward with `before`), not truncated to the newest 100.
- The state file is written atomically; a corrupt state file is logged loudly and
  re-seeds the baseline rather than silently disarming.

Usage:
    python3 alert_watcher.py [--config config.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import config as cfg_mod
import notify

ALERT_LABELS = {"person", "car"}
STATE = Path("~/.sovereign-home/alert_watcher.state").expanduser()
LIMIT = 100
MAX_PAGES = 50  # safety cap: at most LIMIT * MAX_PAGES events drained per run


def _read_state() -> float | None:
    """Saved high-water mark, or None if there's no usable state.

    Missing file -> None (genuine first run). Corrupt file -> None too, but logged
    loudly so a torn write can't silently disarm the watcher.
    """
    if not STATE.exists():
        return None
    try:
        return float(STATE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        print(
            f"[alert_watcher] state file {STATE} unreadable/corrupt ({exc}); "
            f"re-seeding baseline.",
            file=sys.stderr,
        )
        return None


def _save_ts(ts: float) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(str(ts), encoding="utf-8")
    os.replace(tmp, STATE)  # atomic on POSIX — no torn state file


def _start(ev: dict) -> float:
    try:
        return float(ev.get("start_time", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _events(nvr_url: str, after: float, before: float | None = None) -> list[dict]:
    url = f"{nvr_url.rstrip('/')}/api/events?limit={LIMIT}&after={after}"
    if before is not None:
        url += f"&before={before}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, list) else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def _collect_new(nvr_url: str, after: float) -> list[dict]:
    """Every event with start_time > after, drained across pages, ascending.

    Frigate returns at most LIMIT events ordered newest-first, so to get the older
    ones we re-query with `before` set to the current page's oldest, deduping by id.
    """
    collected: dict[str, dict] = {}
    before: float | None = None
    for _ in range(MAX_PAGES):
        events = _events(nvr_url, after, before)
        if not events:
            break
        for ev in events:
            eid = ev.get("id") or f"{ev.get('camera')}:{_start(ev)}"
            collected[eid] = ev
        if len(events) < LIMIT:
            break
        oldest = min(_start(e) for e in events)
        if oldest <= after:
            break
        before = oldest  # next page: older than this page's oldest
    return sorted(collected.values(), key=_start)


def _seed_baseline(nvr_url: str) -> None:
    events = _events(nvr_url, 0.0)
    if events:
        _save_ts(max(_start(e) for e in events))
    print("seeded baseline; no alerts on first run.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Frigate -> Telegram alert watcher")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    args = parser.parse_args()
    cfg = cfg_mod.load_config(args.config)
    nvr_url = cfg.get("sitrep", {}).get("nvr_url", "http://localhost:5000")

    last = _read_state()
    if last is None:  # first run or corrupt -> seed, don't blast history
        _seed_baseline(nvr_url)
        return

    events = _collect_new(nvr_url, last)  # ascending, fully drained
    mark = last
    sent = 0
    stop = False
    for ev in events:
        start = _start(ev)
        if ev.get("label") in ALERT_LABELS:
            cam = ev.get("camera", "camera")
            label = ev.get("label", "object")
            if notify.send(f"\U0001F6A8 {label} at {cam}", cfg):
                mark = max(mark, start)
                sent += 1
            else:
                # leave this + all later events behind the mark; retry next run
                stop = True
                break
        else:
            mark = max(mark, start)

    if mark > last:
        _save_ts(mark)
    tail = " (held — send failed, will retry)" if stop else ""
    print(f"checked {len(events)} event(s) since {last}; sent {sent} alert(s){tail}.")


if __name__ == "__main__":
    main()
