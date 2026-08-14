"""Minimal LLM client (Ollama HTTP API). Zero third-party deps."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def resolve_api_key() -> str:
    """Bearer token for ollama.com (or a protected self-host). Empty = local."""
    return (
        os.environ.get("SOVEREIGN_HOME_OLLAMA_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or ""
    ).strip()


def request_headers(key: str = "") -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def chat(
    ollama_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int = 120,
    api_key: str | None = None,
) -> str:
    """Send a chat completion to Ollama and return the reply text.

    Raises RuntimeError with a friendly hint if Ollama is not reachable.
    When ``OLLAMA_API_KEY`` or ``SOVEREIGN_HOME_OLLAMA_API_KEY`` is set, the
    request carries a Bearer header so ollama.com / tunneled hosts work.
    """
    key = resolve_api_key() if api_key is None else api_key
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers=request_headers(key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Ollama at {ollama_url} returned HTTP {exc.code}. "
            f"If this is ollama.com, set OLLAMA_API_KEY. ({exc})"
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {ollama_url}. Is it running? "
            f"Start it with `ollama serve` and pull the model with "
            f"`ollama pull {model}`. ({exc})"
        ) from exc
    msg = data.get("message") if isinstance(data, dict) else None
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    return content.strip()
