"""Load assistant config from JSON, with sane defaults.

Missing file or missing keys fall back to DEFAULT_CONFIG, so the assistant
runs out of the box before you customize anything.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

DEFAULT_CONFIG: dict = {
    "model": "qwen2.5:7b",
    "ollama_url": "http://localhost:11434",
    "memory_path": "~/.sovereign-home/memory.jsonl",
    "sitrep": {
        "include_system": True,
        "include_nvr": True,
        "nvr_url": "http://localhost:5000",
        "nvr_hours": 24,
    },
}


def load_config(path: str | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not path:
        return cfg
    p = Path(path).expanduser()
    if not p.exists():
        return cfg
    user = json.loads(p.read_text(encoding="utf-8"))
    for key, value in user.items():
        if key == "sitrep" and isinstance(value, dict):
            cfg["sitrep"].update(value)
        else:
            cfg[key] = value
    return cfg
