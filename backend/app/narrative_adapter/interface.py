"""Narrative-generation adapter boundary.

The user has an existing, separate app for narrative generation that will be
wired in later. `stub_azure_impl.py` implements this same Protocol with a
real streaming Azure OpenAI call so the system works end-to-end today. To
swap in the real app: implement this Protocol in a new module and change the
import in app/graph/nodes/narrative.py -- nothing else in the graph needs to
change.
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class NarrativeGenerator(Protocol):
    async def generate(
        self,
        target_type: str,
        insight_type: str,
        question: str,
        data: list[dict[str, Any]],
        narrative_hints: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield narrative text chunks (tokens/sentences) as they're produced."""
        ...
