"""Minimal local LLM client (Ollama HTTP API). Zero third-party deps."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def chat(
    ollama_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int = 120,
) -> str:
    """Send a chat completion to a local Ollama server and return the reply text.

    Raises RuntimeError with a friendly hint if Ollama is not reachable.
    """
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {ollama_url}. Is it running? "
            f"Start it with `ollama serve` and pull the model with "
            f"`ollama pull {model}`. ({exc})"
        ) from exc
    msg = data.get("message") if isinstance(data, dict) else None
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    return content.strip()
