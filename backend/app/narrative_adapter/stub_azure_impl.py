"""=== SWAP POINT ===
Today's real implementation: streams a narrative out of Azure OpenAI given
the fetched data. Replace this module's `generate` with a call into the
user's existing narrative app once its exact interface is available -- the
Protocol in interface.py is the contract app/graph/nodes/narrative.py relies
on, so nothing else needs to change.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from app.llm import get_chat_model

_SYSTEM_PROMPT = """You are a business analyst producing a short natural-language \
narrative summarizing query results for a business user. Be concise, factual, and \
grounded only in the data provided -- never invent numbers. If the data is empty, \
say so plainly."""


async def generate(
    target_type: str,
    insight_type: str,
    question: str,
    data: list[dict[str, Any]],
    narrative_hints: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    hints = narrative_hints or {}
    user_prompt = (
        f"User's question: {question}\n"
        f"Insight type: {insight_type} (target: {target_type})\n"
        f"Tone: {hints.get('tone', 'concise, business-analyst style')}\n"
        f"Emphasize: {', '.join(hints.get('emphasize', [])) or 'key findings'}\n\n"
        f"Row count: {len(data)}\n"
        f"Data (JSON, truncated to first 50 rows):\n{json.dumps(data[:50], default=str)}"
    )

    model = get_chat_model(temperature=0.3, streaming=True)
    async for chunk in model.astream(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    ):
        if chunk.content:
            yield chunk.content
