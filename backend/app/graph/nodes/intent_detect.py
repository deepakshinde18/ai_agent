from dataclasses import asdict
from typing import Literal

from langgraph.types import Command

from app.config import get_settings
from app.graph.state import ErrorInfo, InsightAgentState
from app.rag.intent_matcher import match_intent


async def detect_intent_node(
    state: InsightAgentState,
) -> Command[Literal["clarify", "lookup_intent", "error_handler"]]:
    settings = get_settings()
    try:
        result = match_intent(state["sanitized_input"])
    except Exception as exc:  # noqa: BLE001
        error: ErrorInfo = {
            "node": "detect_intent",
            "code": "UNKNOWN",
            "user_message": "Something went wrong while understanding your request.",
            "internal_detail": repr(exc),
        }
        return Command(goto="error_handler", update={"error": error})

    candidates = [asdict(c) for c in result.candidates]

    if result.top is None:
        error = {
            "node": "detect_intent",
            "code": "INTENT_NOT_FOUND",
            "user_message": "We couldn't match your request to anything we can report on yet.",
            "internal_detail": "no intent examples seeded in Chroma, or empty collection",
        }
        return Command(goto="error_handler", update={"error": error, "intent_candidates": candidates})

    if result.top.confidence < settings.intent_confidence_threshold:
        return Command(
            goto="clarify",
            update={
                "intent_candidates": candidates,
                "intent_confidence": result.top.confidence,
                "needs_clarification": True,
            },
        )

    return Command(
        goto="lookup_intent",
        update={
            "intent_candidates": candidates,
            "resolved_intent": result.top.insight_type,
            "intent_confidence": result.top.confidence,
        },
    )
