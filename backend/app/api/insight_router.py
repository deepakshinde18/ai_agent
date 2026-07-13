import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_graph
from app.auth.dependencies import get_current_user
from app.db.models import User
from app.logging_conf import get_logger
from app.schemas.insight import InsightQueryRequest
from app.schemas.sse import format_sse

router = APIRouter(prefix="/insights", tags=["insights"])
logger = get_logger(__name__)


@router.post("/query")
async def query_insight(
    payload: InsightQueryRequest,
    user: User = Depends(get_current_user),
    graph=Depends(get_graph),
):
    session_id = payload.session_id or str(uuid.uuid4())

    async def event_gen() -> AsyncIterator[str]:
        yield format_sse("session", {"session_id": session_id})

        config = {"configurable": {"thread_id": session_id}}
        input_state = {
            "raw_input": payload.query,
            "user_id": str(user.id),
            "session_id": session_id,
            "started_at_ms": time.time() * 1000,
        }

        try:
            async for mode, chunk in graph.astream(
                input_state, config, stream_mode=["updates", "messages"]
            ):
                if mode == "messages":
                    message_chunk, metadata = chunk
                    if metadata.get("langgraph_node") == "generate_narrative" and message_chunk.content:
                        yield format_sse("token", {"token": message_chunk.content})
                elif mode == "updates":
                    for node_name, update in chunk.items():
                        if not update:
                            continue
                        if node_name == "fill_slots" and "fetched_rows" in update:
                            yield format_sse(
                                "rows",
                                {"rows": update["fetched_rows"], "row_count": update.get("row_count")},
                            )
                        if node_name == "clarify" and update.get("clarification_message"):
                            yield format_sse("clarify", {"message": update["clarification_message"]})
                        if update.get("error"):
                            yield format_sse(
                                "error",
                                {"code": update["error"]["code"], "message": update["error"]["user_message"]},
                            )
            yield format_sse("done", {})
        except Exception as exc:  # noqa: BLE001 -- never let a raw exception reach the client stream
            logger.error("insight_stream_failed", detail=repr(exc), session_id=session_id)
            yield format_sse("error", {"code": "UNKNOWN", "message": "Something went wrong. Please try again."})
            yield format_sse("done", {})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
