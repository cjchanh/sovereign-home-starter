"""Load assistant config from JSON, with sane defaults.

Missing file or missing keys fall back to DEFAULT_CONFIG, so the assistant
runs out of the box before you customize anything.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG: dict = {
    "model": "qwen2.5:7b",
    "ollama_url": "http://127.0.0.1:11434",
    "memory_path": "~/.sovereign-home/memory.jsonl",
    "sitrep": {
        "include_system": True,
        "include_nvr": True,
        "nvr_url": "http://127.0.0.1:5000",
        "nvr_hours": 24,
        "nvr_api_key": "",          # optional: set or export FRIGATE_API_KEY
    },
    "notify": {
        "telegram_bot_token": "",
        "telegram_chat_id": "",
    },
    "alerts": {
        "cooldown_seconds": 120,    # suppress repeat alerts for same camera within this window
        "vision_caption": False,    # optional: run snapshot through a local vision model
        "vision_model": "qwen2.5vl:7b",  # Ollama vision model; pull with: ollama pull qwen2.5vl:7b
        "vision_timeout": 30,       # max seconds per vision call before falling back to a plain alert
    },
}


def _apply_env_overrides(cfg: dict) -> dict:
    """Apply container-friendly overrides without making config files secret-bearing."""
    model = os.environ.get("SOVEREIGN_HOME_MODEL")
    ollama_url = os.environ.get("SOVEREIGN_HOME_OLLAMA_URL")
    memory_path = os.environ.get("SOVEREIGN_HOME_MEMORY_PATH")
    nvr_url = os.environ.get("SOVEREIGN_HOME_NVR_URL")

    if model:
        cfg["model"] = model
    if ollama_url:
        cfg["ollama_url"] = ollama_url
    if memory_path:
        cfg["memory_path"] = memory_path
    if nvr_url:
        cfg["sitrep"]["nvr_url"] = nvr_url
    return cfg


def load_config(path: str | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not path:
        return _apply_env_overrides(cfg)
    p = Path(path).expanduser()
    if not p.exists():
        return _apply_env_overrides(cfg)
    try:
        user = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[!] Ignoring bad config {p}: {exc}. Using defaults.", file=sys.stderr)
        return _apply_env_overrides(cfg)
    if not isinstance(user, dict):
        return _apply_env_overrides(cfg)
    # "sitrep" and "alerts" are deep-merged; every other key replaces wholesale.
    for key, value in user.items():
        if key in ("sitrep", "alerts"):
            if isinstance(value, dict):
                cfg[key].update(value)
            # ignore a non-dict override; keep the defaults
        else:
            cfg[key] = value
    return _apply_env_overrides(cfg)
