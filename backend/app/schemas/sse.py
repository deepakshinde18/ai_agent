import json
from typing import Any, Literal

SseEventType = Literal["session", "token", "rows", "clarify", "error", "done"]


def format_sse(event: SseEventType, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
