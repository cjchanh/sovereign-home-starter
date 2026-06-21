#!/usr/bin/env python3
"""Two-way Telegram bot — lets you text the assistant from your phone.

Long-polls the Telegram getUpdates API (zero deps, urllib) and replies to the
configured chat id only. Understands the same commands as the chat REPL:

    /sitrep            generate your situation report
    /remember <text>   save a note
    /todo <text>       save a todo
    <anything else>    routed to the local model via Ollama

SECURITY: messages from any chat id other than the configured one are silently
ignored. If no bot token or chat id is configured, the bot prints a hint and
exits 0 (fail-soft — doesn't break a service unit restart loop).

Start manually:
    cd assistant && python3 telegram_bot.py [--config config.json]

Or install the systemd unit (see telegram-bot.service.example).
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
import llm
import memory
import notify
import sitrep as sitrep_mod

SYSTEM_PROMPT = (
    "You are a private, local home assistant. You are concise and practical. "
    "You help with day-to-day planning, home systems, and quick questions. "
    "You have access to the user's saved notes below; use them when relevant."
)

_POLL_TIMEOUT = 30   # long-poll seconds (Telegram max is 50)
_RETRY_DELAY = 5     # seconds to wait after a network error before retrying


def _context_block(memory_path: str) -> str:
    notes = memory.load(memory_path, limit=20)
    if not notes:
        return "(no saved notes yet)"
    return "\n".join(f"- [{e.kind}] {e.text}" for e in notes)


def _get_updates(token: str, offset: int) -> list[dict]:
    """Call getUpdates with long-polling. Returns a list of update dicts."""
    url = (
        f"https://api.telegram.org/bot{token}/getUpdates"
        f"?timeout={_POLL_TIMEOUT}&offset={offset}"
    )
    try:
        with urllib.request.urlopen(url, timeout=_POLL_TIMEOUT + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[telegram_bot] getUpdates error: {exc}", file=sys.stderr)
        return []
    if not (isinstance(data, dict) and data.get("ok")):
        print(f"[telegram_bot] getUpdates API error: {data}", file=sys.stderr)
        return []
    return data.get("result", [])


def _handle(text: str, cfg: dict) -> str:
    """Dispatch one incoming text to the right handler; return the reply string."""
    mem_path = cfg["memory_path"]
    text = text.strip()

    if text == "/sitrep":
        return sitrep_mod.build_sitrep(cfg)

    if text.startswith("/remember "):
        note = text[len("/remember "):]
        memory.remember(mem_path, note, kind="note")
        return "saved."

    if text.startswith("/todo "):
        item = text[len("/todo "):]
        memory.remember(mem_path, item, kind="todo")
        return "todo saved."

    # General question — route to local model
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "Saved notes:\n" + _context_block(mem_path)},
        {"role": "user", "content": text},
    ]
    try:
        return llm.chat(cfg["ollama_url"], cfg["model"], messages)
    except RuntimeError as exc:
        return f"[assistant unavailable] {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-way Telegram bot for the local assistant")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    args = parser.parse_args()
    cfg = cfg_mod.load_config(args.config)

    # Read credentials the same way notify does
    n = cfg.get("notify", {}) if isinstance(cfg, dict) else {}
    if not isinstance(n, dict):
        n = {}
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or n.get("telegram_bot_token") or ""
    chat_id = str(
        os.environ.get("TELEGRAM_CHAT_ID") or n.get("telegram_chat_id") or ""
    ).strip()

    if not token or not chat_id:
        print(
            "[telegram_bot] no token/chat configured — nothing to do.\n"
            "Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, or add them to the\n"
            "notify block in assistant/config.json, then re-run.",
            file=sys.stderr,
        )
        sys.exit(0)

    print(f"[telegram_bot] listening (chat_id={chat_id}) …", flush=True)
    offset = 0
    while True:
        try:
            updates = _get_updates(token, offset)
        except Exception as exc:  # unexpected — log and retry
            print(f"[telegram_bot] unexpected error in poll: {exc}", file=sys.stderr)
            time.sleep(_RETRY_DELAY)
            continue

        if not updates:
            # network hiccup or genuine timeout — brief pause to avoid spin
            time.sleep(1)
            continue

        for upd in updates:
            offset = upd.get("update_id", offset) + 1
            msg = upd.get("message") or upd.get("edited_message") or {}
            incoming_chat = str(msg.get("chat", {}).get("id", "")).strip()

            # SECURITY: ignore any message not from the configured chat id
            if incoming_chat != chat_id:
                continue

            text = msg.get("text", "")
            if not text:
                continue

            reply = _handle(text, cfg)
            if not notify.send(reply, cfg):
                print(
                    f"[telegram_bot] failed to send reply for: {text!r}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    main()
