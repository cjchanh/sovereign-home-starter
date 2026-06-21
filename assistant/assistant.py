#!/usr/bin/env python3
"""sovereign-home — local private assistant.

Talks to a local model (Ollama), remembers what you tell it, and can generate a
sitrep on demand. Nothing leaves your machine.

Usage:
    python3 assistant.py [--config config.json]

In the chat:
    /remember <text>   save a note to local memory
    /todo <text>       save a todo
    /sitrep            generate your situation report now
    /quit              exit
"""
from __future__ import annotations

import argparse
from pathlib import Path

import config as cfg_mod
import llm
import memory
import sitrep as sitrep_mod

SYSTEM_PROMPT = (
    "You are a private, local home assistant. You are concise and practical. "
    "You help with day-to-day planning, home systems, and quick questions. "
    "You have access to the user's saved notes below; use them when relevant."
)


def _context_block(memory_path: str) -> str:
    notes = memory.load(memory_path, limit=20)
    if not notes:
        return "(no saved notes yet)"
    return "\n".join(f"- [{e.kind}] {e.text}" for e in notes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local private home assistant")
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "config.json")
    )
    args = parser.parse_args()

    cfg = cfg_mod.load_config(args.config)
    mem_path = cfg["memory_path"]

    print("sovereign-home assistant — local + private. Type /quit to exit.\n")
    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break
        if user.startswith("/remember "):
            memory.remember(mem_path, user[len("/remember "):], kind="note")
            print("saved.\n")
            continue
        if user.startswith("/todo "):
            memory.remember(mem_path, user[len("/todo "):], kind="todo")
            print("todo saved.\n")
            continue
        if user == "/sitrep":
            print(sitrep_mod.build_sitrep(cfg) + "\n")
            continue

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "Saved notes:\n" + _context_block(mem_path)},
            {"role": "user", "content": user},
        ]
        try:
            reply = llm.chat(cfg["ollama_url"], cfg["model"], messages)
        except RuntimeError as exc:
            print(f"\n[!] {exc}\n")
            continue
        print(f"\nassistant > {reply}\n")


if __name__ == "__main__":
    main()
