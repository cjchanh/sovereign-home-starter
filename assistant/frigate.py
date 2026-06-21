"""Centralized Frigate HTTP helper.

All calls to the Frigate API go through ``frigate_get``, which:
- builds a ``urllib.request.Request`` for the given URL,
- adds ``Authorization: Bearer <key>`` when a non-empty key is supplied,
- preserves existing fail-soft behaviour (URLError / TimeoutError /
  JSONDecodeError → caller-defined default, never raises).

The API key is resolved once by ``get_api_key``:
    1. ``FRIGATE_API_KEY`` environment variable (highest priority),
    2. ``cfg["sitrep"]["nvr_api_key"]`` from the loaded config dict,
    3. empty string → no header added.

Zero third-party deps; stdlib only.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def get_api_key(cfg: dict | None) -> str:
    """Return the Frigate API key to use, or '' if none is configured.

    Env var FRIGATE_API_KEY overrides the config file value.
    """
    env_key = os.environ.get("FRIGATE_API_KEY", "")
    if env_key:
        return env_key
    if isinstance(cfg, dict):
        sitrep = cfg.get("sitrep", {})
        if isinstance(sitrep, dict):
            return str(sitrep.get("nvr_api_key", "") or "")
    return ""


def frigate_get(url: str, api_key: str, timeout: int = 10) -> urllib.request.Request:
    """Build a ``urllib.request.Request`` for *url*, optionally with Bearer auth.

    Returns the Request object — callers open it themselves so they can decide
    what to do with the response body (JSON parse, raw bytes, etc.).
    """
    req = urllib.request.Request(url, method="GET")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    return req


def fetch_json(url: str, api_key: str, timeout: int = 10) -> list | dict | None:
    """GET *url*, add auth if *api_key* is set, parse JSON.

    Returns the parsed object on success; ``None`` on any error (fail-soft).
    """
    req = frigate_get(url, api_key, timeout=timeout)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def fetch_bytes(url: str, api_key: str, timeout: int = 10) -> bytes | None:
    """GET *url*, add auth if *api_key* is set, return raw bytes.

    Returns bytes on success; ``None`` on any error (fail-soft).
    """
    req = frigate_get(url, api_key, timeout=timeout)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return data if data else None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
