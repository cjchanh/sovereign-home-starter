"""Send notifications to Telegram (sitrep + camera alerts). Zero deps, fail-soft.

Credentials come from env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) or, for cron
reliability, the `notify` block in config.json. If they're missing, send() is a
no-op that prints a hint to stderr and returns False — it never raises, so a
missing token degrades gracefully instead of breaking a cron job.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

_TELEGRAM_MAX = 4096


def _creds(cfg: dict | None) -> tuple[str | None, str | None]:
    n = cfg.get("notify", {}) if isinstance(cfg, dict) else {}
    if not isinstance(n, dict):
        n = {}
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or n.get("telegram_bot_token") or ""
    chat = os.environ.get("TELEGRAM_CHAT_ID") or n.get("telegram_chat_id") or ""
    return (token or None), (chat or None)


def send(text: str, cfg: dict | None = None) -> bool:
    """Push one message to Telegram. Returns True on success, False (no raise) otherwise."""
    token, chat = _creds(cfg)
    if not token or not chat:
        print(
            "[notify] no Telegram token/chat set — skipping. Set TELEGRAM_BOT_TOKEN + "
            "TELEGRAM_CHAT_ID, or the notify block in config.json.",
            file=sys.stderr,
        )
        return False
    if len(text) > _TELEGRAM_MAX:
        text = text[: _TELEGRAM_MAX - 20] + "\n…(truncated)"
    payload = json.dumps(
        {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[notify] could not reach Telegram: {exc}", file=sys.stderr)
        return False
    if not (isinstance(data, dict) and data.get("ok")):
        print(f"[notify] Telegram API error: {data}", file=sys.stderr)
        return False
    return True
