from app.graph.state import InsightAgentState
from app.logging_conf import get_logger

logger = get_logger(__name__)


async def error_handler_node(state: InsightAgentState) -> dict:
    error = state.get("error")
    if error:
        logger.warning(
            "agent_error",
            node=error["node"],
            code=error["code"],
            detail=error["internal_detail"],
            session_id=state.get("session_id"),
        )
    # error.user_message is already safe for the client; nothing to transform.
    return {}


if __name__ == "__main__":
    import asyncio

    sample_state = {
        "session_id": "test-session",
        "error": {
            "node": "fill_slots",
            "code": "SLOT_RESOLUTION_FAILED",
            "user_message": "Couldn't fully understand the filters in your request.",
            "internal_detail": "SlotResolutionError('...')",
        },
    }
    print(asyncio.run(error_handler_node(sample_state)))
