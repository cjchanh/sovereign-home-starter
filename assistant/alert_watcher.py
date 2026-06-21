#!/usr/bin/env python3
"""Watch Frigate for new person/car events and push a Telegram alert for each.

One-shot by design: each run alerts on events newer than the previous run, then
records the high-water mark to a small state file. Run it from cron every minute
or two — no long-running daemon to babysit. The first run only seeds the baseline
(no alert blast for historical events).

Usage:
    python3 alert_watcher.py [--config config.json]
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import config as cfg_mod
import notify

ALERT_LABELS = {"person", "car"}
STATE = Path("~/.sovereign-home/alert_watcher.state").expanduser()


def _last_ts() -> float:
    try:
        return float(STATE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0.0


def _save_ts(ts: float) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(str(ts), encoding="utf-8")


def _events(nvr_url: str, after: float) -> list[dict]:
    url = f"{nvr_url.rstrip('/')}/api/events?limit=100&after={after}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, list) else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def _start(ev: dict) -> float:
    try:
        return float(ev.get("start_time", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Frigate -> Telegram alert watcher")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    args = parser.parse_args()
    cfg = cfg_mod.load_config(args.config)
    nvr_url = cfg.get("sitrep", {}).get("nvr_url", "http://localhost:5000")

    last = _last_ts()
    events = _events(nvr_url, last)

    # First run: seed the baseline, do NOT alert on historical events.
    if last == 0.0:
        if events:
            _save_ts(max(_start(e) for e in events))
        print("seeded baseline; no alerts on first run.")
        return

    newest = last
    sent = 0
    for ev in sorted(events, key=_start):
        start = _start(ev)
        newest = max(newest, start)
        if ev.get("label") in ALERT_LABELS and start > last:
            cam = ev.get("camera", "camera")
            label = ev.get("label", "object")
            if notify.send(f"\U0001F6A8 {label} at {cam}", cfg):
                sent += 1
    if newest > last:
        _save_ts(newest)
    print(f"checked {len(events)} event(s) since {last}; sent {sent} alert(s).")


if __name__ == "__main__":
    main()
