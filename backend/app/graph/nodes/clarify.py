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


if __name__ == "__main__":
    import asyncio

    sample_state = {
        "intent_candidates": [
            {"insight_type": "clients_by_balance_city", "example_text": "clients over 1m", "confidence": 0.4},
            {
                "insight_type": "accounts_by_brokerage_sweep_cash",
                "example_text": "accounts by sweep cash",
                "confidence": 0.35,
            },
        ]
    }
    print(asyncio.run(clarify_node(sample_state)))
