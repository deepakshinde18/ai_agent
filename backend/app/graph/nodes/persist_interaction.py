import time

from app.db.models import Interaction
from app.db.session import AgentSessionLocal
from app.graph.state import InsightAgentState
from app.logging_conf import get_logger

logger = get_logger(__name__)


async def persist_interaction_node(state: InsightAgentState) -> dict:
    duration_ms = None
    started_at_ms = state.get("started_at_ms")
    if started_at_ms:
        duration_ms = int((time.time() * 1000) - started_at_ms)

    error = state.get("error")
    try:
        async with AgentSessionLocal() as session:
            session.add(
                Interaction(
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    raw_input_redacted=state.get("sanitized_input") or state.get("raw_input", ""),
                    resolved_intent=state.get("resolved_intent"),
                    intent_confidence=state.get("intent_confidence"),
                    sql_executed=state.get("final_sql"),
                    row_count=state.get("row_count"),
                    narrative_output=state.get("narrative_complete"),
                    error_code=error["code"] if error else None,
                    error_message=error["user_message"] if error else None,
                    duration_ms=duration_ms,
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 -- audit-log failure must never crash the response
        logger.error("persist_interaction_failed", detail=repr(exc), session_id=state.get("session_id"))

    return {}
