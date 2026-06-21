"""Local vision-model captioning via Ollama. Zero third-party deps, fail-soft.

The snapshot bytes are sent only to the local Ollama instance — they never leave
the box. If the vision model is slow, unavailable, or returns garbage, this module
returns None and the caller falls back to the plain alert. It never raises.
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request

_PROMPT = (
    "Describe who or what is in this security camera frame in one short sentence."
)


def describe_image(
    ollama_url: str,
    model: str,
    image_bytes: bytes,
    timeout: int = 60,
) -> str | None:
    """Send *image_bytes* to a local Ollama vision model and return a one-line caption.

    The image is base64-encoded and included directly in the chat message — no temp
    files, no external calls. The snapshot never leaves the host.

    Returns the caption string on success, or None on any failure (network error,
    timeout, model not pulled, empty/garbage response, JSON error). Callers must
    treat None as "no caption available" and fall back to the plain alert.
    """
    if not image_bytes:
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": _PROMPT,
                    "images": [b64],
                }
            ],
            "stream": False,
        }
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
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"[vision] caption failed: {exc}", file=sys.stderr)
        return None

    # Null-safe extraction: same pattern as llm.py
    msg = data.get("message") if isinstance(data, dict) else None
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    text = content.strip() if isinstance(content, str) else ""
    if not text:
        print("[vision] empty response from vision model — skipping caption.", file=sys.stderr)
        return None
    return text
