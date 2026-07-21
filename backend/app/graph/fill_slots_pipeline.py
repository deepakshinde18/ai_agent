"""Runs the graph's sanitize -> detect_intent -> lookup_intent -> fill_slots
segment on its own, without the narrative/persist stages, for callers (e.g.
the MCP tool) that only need the built SQL and fetched rows for a piece of
natural-language input.

Reuses the same node functions as app.graph.build's full graph unchanged --
this just stops short of generate_narrative/persist_interaction.
"""

import time
import uuid

from app.graph.nodes.clarify import clarify_node
from app.graph.nodes.fill_slots import fill_slots_node
from app.graph.nodes.intent_detect import detect_intent_node
from app.graph.nodes.intent_lookup import lookup_intent_node
from app.graph.nodes.sanitize import sanitize_node
from app.graph.state import InsightAgentState


def _error_result(state: InsightAgentState) -> dict:
    error = state["error"]
    return {"error": {"code": error["code"], "message": error["user_message"]}}


async def run_fill_slots(raw_input: str, session_id: str | None = None) -> dict:
    """Runs sanitize -> detect_intent -> lookup_intent -> fill_slots for one request."""
    session_id = session_id or str(uuid.uuid4())
    state: InsightAgentState = {
        "raw_input": raw_input,
        "session_id": session_id,
        "started_at_ms": time.time() * 1000,
    }

    state.update(await sanitize_node(state))
    if state.get("error"):
        return _error_result(state)

    command = await detect_intent_node(state)
    state.update(command.update or {})
    if command.goto == "error_handler":
        return _error_result(state)
    if command.goto == "clarify":
        state.update(await clarify_node(state))
        return {"needs_clarification": True, "message": state.get("clarification_message")}

    state.update(await lookup_intent_node(state))
    if state.get("error"):
        return _error_result(state)

    state.update(await fill_slots_node(state))
    if state.get("error"):
        return _error_result(state)

    return {
        "sql": state.get("final_sql"),
        "sql_params": state.get("sql_params"),
        "rows": state.get("fetched_rows"),
        "row_count": state.get("row_count"),
    }
