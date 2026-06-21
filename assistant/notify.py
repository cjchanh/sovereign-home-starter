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

_TELEGRAM_MAX = 4096         # Telegram message text limit in UTF-16 code units
_TELEGRAM_CAPTION_MAX = 1024  # Telegram sendPhoto caption limit in UTF-16 code units


def _u16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _creds(cfg: dict | None) -> tuple[str | None, str | None]:
    n = cfg.get("notify", {}) if isinstance(cfg, dict) else {}
    if not isinstance(n, dict):
        n = {}
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or n.get("telegram_bot_token") or ""
    chat = os.environ.get("TELEGRAM_CHAT_ID") or n.get("telegram_chat_id") or ""
    return (token or None), (chat or None)


def _truncate_utf16(text: str, max_units: int) -> str:
    """Truncate *text* so it fits within *max_units* UTF-16 code units."""
    if _u16_len(text) <= max_units:
        return text
    marker = "\n…(truncated)"
    budget = max_units - _u16_len(marker)
    while text and _u16_len(text) > budget:
        text = text[:-1]
    return text + marker


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
    text = _truncate_utf16(text, _TELEGRAM_MAX)
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


def send_photo(caption: str, image_bytes: bytes, cfg: dict | None = None) -> bool:
    """Push a photo with caption to Telegram via sendPhoto (multipart/form-data).

    Builds the multipart body by hand — no third-party deps.  Returns True on
    success, False (no raise) on any failure, matching the fail-soft contract of
    send(). Caption is truncated to the Telegram photo-caption limit (1024 UTF-16
    code units) before sending.
    """
    token, chat = _creds(cfg)
    if not token or not chat:
        print(
            "[notify] no Telegram token/chat set — skipping send_photo. "
            "Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, or the notify block in config.json.",
            file=sys.stderr,
        )
        return False

    # Telegram photo captions are limited to 1024 UTF-16 code units (not 4096).
    caption = _truncate_utf16(caption, _TELEGRAM_CAPTION_MAX)

    boundary = "----SovereignHomeBoundary"
    crlf = b"\r\n"

    def _part_field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"\r\n"
            f"{value}\r\n"
        ).encode("utf-8")

    def _part_file(name: str, filename: str, data: bytes, content_type: str) -> bytes:
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n"
        ).encode("utf-8")
        return header + data + crlf

    body = (
        _part_field("chat_id", chat)
        + _part_field("caption", caption)
        + _part_file("photo", "snapshot.jpg", image_bytes, "image/jpeg")
        + f"--{boundary}--\r\n".encode("utf-8")
    )

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[notify] send_photo failed: {exc}", file=sys.stderr)
        return False
    if not (isinstance(data, dict) and data.get("ok")):
        print(f"[notify] Telegram sendPhoto API error: {data}", file=sys.stderr)
        return False
    return True
