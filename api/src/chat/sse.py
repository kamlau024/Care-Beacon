"""Server-Sent Events framing."""

import json


def frame(event: str, data: dict) -> str:
    """One SSE frame: ``event: {event}\\ndata: {compact json}\\n\\n``."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
