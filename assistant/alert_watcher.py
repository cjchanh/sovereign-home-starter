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
- For each alert, we attempt to attach the Frigate snapshot photo. If the photo
  fetch fails, we fall back to a plain text alert. "Delivered" = photo OR text
  fallback succeeded; only a total failure (both paths) holds the mark.

Cooldown:
- After delivering an alert for a camera, further alerts from the SAME camera whose
  start_time falls within cfg["alerts"]["cooldown_seconds"] of the last delivery are
  suppressed (not retried — they still advance the high-water mark).
- Cooldown only applies when there has been a prior delivery for that camera in this
  or a previous run. A camera with no prior delivery is never suppressed.
- Events on different cameras are never throttled by another camera's cooldown.
- The last-delivery timestamp per camera is persisted in a sibling JSON state file
  across cron runs.

Vision caption (optional):
- When cfg["alerts"]["vision_caption"] is true and a snapshot was fetched, the
  snapshot is sent to a LOCAL Ollama vision model to produce a one-line description.
  The image never leaves the box — it goes to local Ollama only.
- A slow or unavailable vision model returns None; the plain caption is sent
  unchanged. Vision failure never blocks or drops an alert.

Usage:
    python3 alert_watcher.py [--config config.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import config as cfg_mod
import frigate as frigate_mod
import notify
import vision

ALERT_LABELS = {"person", "car"}
# State dir is env-overridable so it can live on a persistent volume in a container
# (compose sets SOVEREIGN_HOME_STATE_DIR=/state). Without this, a containerized
# run writes state to an ephemeral ~/.sovereign-home and re-seeds the baseline every
# run — silently never alerting. Default is the host path; unchanged for host/cron use.
_STATE_DIR = Path(os.environ.get("SOVEREIGN_HOME_STATE_DIR", "~/.sovereign-home")).expanduser()
STATE = _STATE_DIR / "alert_watcher.state"
COOLDOWN_STATE = _STATE_DIR / "alert_watcher.cooldown.json"
LIMIT = 100
MAX_PAGES = 50  # safety cap: at most LIMIT * MAX_PAGES events drained per run


# ---------------------------------------------------------------------------
# High-water mark state
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-camera cooldown state
# ---------------------------------------------------------------------------

def _read_cooldown() -> dict[str, float]:
    """Load the per-camera last-delivery map. Returns {} on missing or corrupt."""
    if not COOLDOWN_STATE.exists():
        return {}
    try:
        data = json.loads(COOLDOWN_STATE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: float(v) for k, v in data.items()}
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {}


def _save_cooldown(cd: dict[str, float]) -> None:
    COOLDOWN_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = COOLDOWN_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cd), encoding="utf-8")
    os.replace(tmp, COOLDOWN_STATE)  # atomic


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _start(ev: dict) -> float:
    try:
        return float(ev.get("start_time", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _events(nvr_url: str, after: float, before: float | None = None, api_key: str = "") -> list[dict]:
    url = f"{nvr_url.rstrip('/')}/api/events?limit={LIMIT}&after={after}"
    if before is not None:
        url += f"&before={before}"
    result = frigate_mod.fetch_json(url, api_key, timeout=10)
    return result if isinstance(result, list) else []


def _collect_new(nvr_url: str, after: float, api_key: str = "") -> list[dict]:
    """Every event with start_time > after, drained across pages, ascending.

    Frigate returns at most LIMIT events ordered newest-first, so to get the older
    ones we re-query with `before` set to the current page's oldest, deduping by id.
    """
    collected: dict[str, dict] = {}
    before: float | None = None
    for _ in range(MAX_PAGES):
        events = _events(nvr_url, after, before, api_key)
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


def _fetch_snapshot(nvr_url: str, event_id: str, api_key: str = "") -> bytes | None:
    """Fetch the Frigate snapshot for event_id. Returns bytes or None on failure."""
    url = f"{nvr_url.rstrip('/')}/api/events/{event_id}/snapshot.jpg"
    return frigate_mod.fetch_bytes(url, api_key, timeout=10)


def _send_alert(
    nvr_url: str,
    ev: dict,
    cfg: dict,
    api_key: str = "",
) -> bool:
    """Deliver one alert — photo with caption, falling back to text.

    When cfg["alerts"]["vision_caption"] is true and a snapshot was successfully
    fetched, the snapshot is passed to a local Ollama vision model for a one-line
    description. The description is appended to the caption when available. Vision
    failure (None return) silently falls back to the plain caption — it never
    blocks delivery or changes the delivered/not-delivered outcome.

    Returns True if the alert was delivered by either path, False if both failed.
    """
    cam = ev.get("camera", "camera")
    label = ev.get("label", "object")
    caption = f"\U0001F6A8 {label} at {cam}"
    event_id = ev.get("id")

    alerts_cfg = cfg.get("alerts", {})
    vision_enabled = bool(alerts_cfg.get("vision_caption", False))
    vision_model = str(alerts_cfg.get("vision_model", "qwen3-vl:8b"))
    try:
        vision_timeout = float(alerts_cfg.get("vision_timeout", 30))
    except (TypeError, ValueError):
        vision_timeout = 30.0
    ollama_url = str(cfg.get("ollama_url", "http://127.0.0.1:11434"))

    if event_id:
        snapshot = _fetch_snapshot(nvr_url, event_id, api_key)
        if snapshot is not None:
            # Optional: enrich caption with a local vision description. Bounded by
            # vision_timeout so a slow model can't stall the run more than that per alert.
            if vision_enabled:
                description = vision.describe_image(
                    ollama_url, vision_model, snapshot, timeout=vision_timeout
                )
                if description:
                    caption = f"{caption}\n{description}"
            if notify.send_photo(caption, snapshot, cfg):
                return True
            # photo send failed — fall through to text

    # Text fallback (uses caption as built above, including vision description if any)
    return notify.send(caption, cfg)


def _seed_baseline(nvr_url: str, api_key: str = "") -> None:
    # Seed the high-water mark so we don't blast history on first run, but never
    # leave it unset: if Frigate has no events yet, anchor to "now" so the FIRST
    # real event afterward is > the mark and DOES alert. (Anchoring to the latest
    # existing event when there is history; to now() when there isn't.)
    events = _events(nvr_url, 0.0, api_key=api_key)
    baseline = max((_start(e) for e in events), default=time.time())
    _save_ts(baseline)
    print("seeded baseline; no alerts on first run.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Frigate -> Telegram alert watcher")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    args = parser.parse_args()
    cfg = cfg_mod.load_config(args.config)
    nvr_url = cfg.get("sitrep", {}).get("nvr_url", "http://127.0.0.1:5000")
    api_key = frigate_mod.get_api_key(cfg)
    try:
        cooldown_secs = float(cfg.get("alerts", {}).get("cooldown_seconds", 120))
    except (TypeError, ValueError):
        # A typo'd config (string / null) must not crash a cron-run security alerter.
        print(
            "[alert_watcher] bad alerts.cooldown_seconds; using default 120.",
            file=sys.stderr,
        )
        cooldown_secs = 120.0

    last = _read_state()
    if last is None:  # first run or corrupt -> seed, don't blast history
        _seed_baseline(nvr_url, api_key)
        return

    events = _collect_new(nvr_url, last, api_key)  # ascending, fully drained
    cooldown_map = _read_cooldown()

    mark = last
    sent = 0
    stop = False
    for ev in events:
        start = _start(ev)
        cam = ev.get("camera", "camera")

        if ev.get("label") in ALERT_LABELS:
            # Check per-camera cooldown.
            # Only suppress when a prior delivery exists for this camera AND
            # the interval since that delivery is within the cooldown window.
            # A camera with no entry in cooldown_map has never been alerted —
            # it is never suppressed (cam not in cooldown_map -> first delivery).
            if cam in cooldown_map and (start - cooldown_map[cam]) < cooldown_secs:
                # Suppressed by cooldown: advance mark, do NOT retry next run.
                mark = max(mark, start)
                continue

            # Attempt delivery
            if _send_alert(nvr_url, ev, cfg, api_key):
                cooldown_map[cam] = start
                mark = max(mark, start)
                sent += 1
            else:
                # Leave this + all later events behind the mark; retry next run.
                # Do NOT update cooldown_map — delivery never happened.
                stop = True
                break
        else:
            mark = max(mark, start)

    if mark > last:
        _save_ts(mark)
    _save_cooldown(cooldown_map)
    tail = " (held — send failed, will retry)" if stop else ""
    print(f"checked {len(events)} event(s) since {last}; sent {sent} alert(s){tail}.")


if __name__ == "__main__":
    main()
