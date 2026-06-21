#!/usr/bin/env python3
"""Assemble a situation report from local sources.

Pulls system health, recent NVR (Frigate) events, and your saved todos, then
asks the local model to summarize them into a short brief. Run directly (e.g.
from cron) or via the assistant's /sitrep command.

Usage:
    python3 sitrep.py [--config config.json]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

import config as cfg_mod
import frigate as frigate_mod
import llm
import memory


def _system_health() -> str:
    lines: list[str] = []
    try:
        result = subprocess.run(
            ["uptime"], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            lines.append(f"uptime: {result.stdout.strip()}")
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        total, used, _free = shutil.disk_usage("/")
        pct = used / total * 100
        lines.append(
            f"disk: {used // (1024 ** 3)}G used of {total // (1024 ** 3)}G "
            f"({pct:.0f}%)"
        )
    except OSError:
        pass
    return "\n".join(lines) if lines else "(system health unavailable)"


def _nvr_events(nvr_url: str, hours: int, api_key: str = "") -> str:
    # Actually bound to the window — `after` is a unix timestamp, so the brief's
    # "last Nh" matches the data instead of just "the last 50 events, whenever".
    after = time.time() - hours * 3600
    url = f"{nvr_url.rstrip('/')}/api/events?limit=100&after={after}"
    events = frigate_mod.fetch_json(url, api_key, timeout=10)
    if events is None:
        return "(NVR not reachable — skipping camera summary)"
    if not events:
        return f"no camera events in the last {hours}h."
    counts: dict[str, int] = {}
    for ev in events:
        label = ev.get("label", "object")
        camera = ev.get("camera", "camera")
        key = f"{label} @ {camera}"
        counts[key] = counts.get(key, 0) + 1
    return "\n".join(
        f"- {n}x {k}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1])
    )


def build_sitrep(cfg: dict) -> str:
    parts: list[str] = []
    s = cfg.get("sitrep", {})
    api_key = frigate_mod.get_api_key(cfg)
    if s.get("include_system", True):
        parts.append("## System\n" + _system_health())
    if s.get("include_nvr", True):
        hours = s.get("nvr_hours", 24)
        parts.append(
            f"## Cameras (last {hours}h)\n"
            + _nvr_events(s.get("nvr_url", "http://localhost:5000"), hours, api_key)
        )
    todos = memory.load(cfg["memory_path"], kind="todo")
    if todos:
        parts.append("## Todos\n" + "\n".join(f"- {t.text}" for t in todos))

    raw = "\n\n".join(parts)
    messages = [
        {
            "role": "system",
            "content": (
                "You are writing a short morning situation report for the home "
                "operator. Be concise and practical. Lead with anything that "
                "needs attention. Use only the raw data below; do not invent "
                "anything."
            ),
        },
        {"role": "user", "content": raw},
    ]
    try:
        return llm.chat(cfg["ollama_url"], cfg["model"], messages)
    except RuntimeError:
        # Model unavailable — return the raw brief rather than fail.
        return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local sitrep")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    parser.add_argument(
        "--notify", action="store_true", help="also push the sitrep to Telegram"
    )
    args = parser.parse_args()
    cfg = cfg_mod.load_config(args.config)
    text = build_sitrep(cfg)
    print(text)
    if args.notify:
        import notify

        notify.send("Morning sitrep\n\n" + text, cfg)


if __name__ == "__main__":
    main()
