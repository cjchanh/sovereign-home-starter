"""Local, private memory store for the assistant.

Append-only JSONL on local disk. Nothing leaves the machine.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class MemoryEntry:
    ts: float
    kind: str  # "note" | "todo" | "fact" | "event"
    text: str


def _store_path(path: str) -> Path:
    p = Path(path).expanduser()
    # Your notes/todos are personal — keep the dir owner-only (not the 0755 a
    # default umask would give it).
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.parent.chmod(0o700)
    except OSError:
        pass
    return p


def remember(path: str, text: str, kind: str = "note") -> MemoryEntry:
    """Append one entry to the local memory store and return it."""
    entry = MemoryEntry(ts=time.time(), kind=kind, text=text.strip())
    store = _store_path(path)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")
    # Lock the file owner-only (default umask would leave it 0644 = world-readable).
    try:
        store.chmod(0o600)
    except OSError:
        pass
    return entry


def load(
    path: str,
    limit: int | None = None,
    kind: str | None = None,
) -> list[MemoryEntry]:
    """Load entries from the store, optionally filtered by kind and tail-limited."""
    store = Path(path).expanduser()
    if not store.exists():
        return []
    entries: list[MemoryEntry] = []
    with store.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(MemoryEntry(**data))
            except (json.JSONDecodeError, TypeError):
                continue  # skip malformed lines rather than crash
    if kind:
        entries = [e for e in entries if e.kind == kind]
    if limit is not None:
        entries = entries[-limit:]
    return entries
