from app.graph.state import InsightAgentState


async def clarify_node(state: InsightAgentState) -> dict:
    candidates = state.get("intent_candidates", [])
    options = sorted({c["insight_type"] for c in candidates})
    if options:
        message = (
            "I couldn't confidently determine what you're asking for. "
            f"Did you mean one of: {', '.join(options)}?"
        )
    else:
        message = "I couldn't understand your request well enough to proceed. Could you rephrase it?"
    return {"clarification_message": message}
